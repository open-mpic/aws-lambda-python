import dns.name
import dns.resolver
import json
import os

# Load the default CAA domain list.
default_caa_domain_list = os.environ['default_caa_domains'].split("|")


# pseudocode for CAA RRset search (RFC 8659):
# RelevantCAASet(domain):
#      while domain is not ".":
#       if CAA(domain) is not Empty:
#          return CAA(domain)
#       domain = Parent(domain)
#      return Empty


def check_value_list_permits_issuance(value_list, caa_domains):
    for value in value_list:
        # We currently do not have any parsing for CAA extensions, so we will never accept a value with a extension.
        if ";" in value:
            continue
        # One of the CAA records in this set was an exact match on a CAA domain
        value_no_whitespace = value.strip()
        if value_no_whitespace in caa_domains:
            return True
    # If nothing matched, we cannot issue.
    return False


ISSUE_TAG = 'issue'
ISSUEWILD_TAG = 'issuewild'

# Todo: format perspective response to match API description.
def lambda_handler(event, context):

    caa_params = event['caa-params']

    # Assume the default system configured identifiers and override if sent in the API call.
    caa_identifiers = default_caa_domain_list
    if 'caa-domains' in caa_params:
        caa_identifiers = caa_params['caa-domains']

    domain = dns.name.from_text(event['identifier'])
    

    # Use the cert type field to check if the domain is a wildcard.
    is_wc_domain = False
    if 'certificate-type' in caa_params:
        cert_type = caa_params['certificate-type']
        if cert_type not in ['tls-server', 'tls-server:wildcard']:
            raise ValueError(f"Invalid cert type: {cert_type}")
        is_wc_domain = cert_type == 'tls-server:wildcard'


    caa_found = False
    valid_for_issue = True
    
    while (domain != dns.name.root):
        try:
            lookup = dns.resolver.resolve(domain, dns.rdatatype.CAA)
            print(f'Found a CAA record for {domain}! Response: {lookup.rrset.to_text()}')
            rrset = lookup.rrset
            caa_found = True
            break
        except dns.resolver.NoAnswer:
            print(f'No CAA record found for {domain}; trying parent domain...')
            domain = domain.parent()
        

    # if domain has no CAA records: valid for issuance
    if not caa_found:
        return {
            'statusCode': 200,
            'body': json.dumps({
                'Region': os.environ['AWS_REGION'],
                'ValidForIssue': valid_for_issue,
                'Details': {
                    'Present': False
                }
            })
        }
    
    
    issue_tags = []
    issue_wild_tags = []
    has_unknown_critical_flags = False
    for rr in rrset:
        tag = rr.tag.decode('utf-8')
        val = rr.value.decode('utf-8')
        flags = rr.flags
        if tag == ISSUE_TAG:
            issue_tags.append(val)
        elif tag == ISSUEWILD_TAG:
            issue_wild_tags.append(val)
        elif flags & 0b10000000:
            has_unknown_critical_flags = True
    

    if has_unknown_critical_flags:
        valid_for_issue = False
    else:
        if is_wc_domain and len(issue_wild_tags) > 0:
            valid_for_issue = check_value_list_permits_issuance(issue_wild_tags, caa_identifiers)
        elif len(issue_tags) > 0:
            valid_for_issue = check_value_list_permits_issuance(issue_tags, caa_identifiers)
        else:
            # We had no unknown critical tags and we found no issue tags. Issuance can proceed.
            valid_for_issue = True


    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'Region': os.environ['AWS_REGION'],
            'ValidForIssue': valid_for_issue,
            'Details': {
                    'Present': True,
                    'FoundAt': domain.to_text(omit_final_dot=True),
                    'Response': rrset.to_text()
                }
        })
    }