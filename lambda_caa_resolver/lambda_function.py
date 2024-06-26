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
    
    
    
    caa_tags_seen = {}
    
    for rr in rrset:
        tag = rr.tag.decode('utf-8')
        val = rr.value.decode('utf-8')
        if tag in caa_tags_seen:
            prev_flags, prev_vals = caa_tags_seen[tag]
            prev_vals.append(val)
            caa_tags_seen[tag] = (rr.flags | prev_flags, prev_vals)
        else:
            caa_tags_seen[tag] = (rr.flags, [val])
    
    # Todo: check this logic.
    for tag, (flags, val) in caa_tags_seen.items():
        if tag == ISSUE_TAG and not is_wc_domain:
            
            valid_for_issue &= any([id_ in val for id_ in caa_identifiers])
            print(f'Hit processing for issue tag. Still valid to issue? {valid_for_issue}')
        elif tag == ISSUEWILD_TAG and is_wc_domain:
            valid_for_issue &= any([id_ in val for id_ in caa_identifiers])
            print(f'Hit processing for issuewild tag. Still valid to issue? {valid_for_issue}')
        elif flags & 0b10000000: # case for unknown tag, critical bit sent
            valid_for_issue = False
            
    
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