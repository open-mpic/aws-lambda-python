import json
import os
from typing import Final

import dns

ISSUE_TAG: Final[str] = 'issue'
ISSUEWILD_TAG: Final[str] = 'issuewild'


class MpicCaaChecker:
    def __init__(self):
        self.default_caa_domain_list = os.environ['default_caa_domains'].split("|")

    @staticmethod
    def does_value_list_permit_issuance(value_list: list, caa_domains):
        for value in value_list:
            # We currently do not have any parsing for CAA extensions, so we will never accept a value with an extension.
            if ";" in value:
                continue
            # One of the CAA records in this set was an exact match on a CAA domain
            value_no_whitespace = value.strip()
            if value_no_whitespace in caa_domains:
                return True
        # If nothing matched, we cannot issue.
        return False

    def execute_caa_check(self, event):
        caa_params = event['caa_params']

        # Assume the default system configured validation targets and override if sent in the API call.
        caa_domains = self.default_caa_domain_list
        if 'caa_domains' in caa_params:
            caa_domains = caa_params['caa_domains']

        domain = dns.name.from_text(event['domain_or_ip_target'])

        # Use the cert type field to check if the domain is a wildcard.
        is_wc_domain = False
        if 'certificate_type' in caa_params:
            cert_type = caa_params['certificate_type']
            if cert_type not in ['tls_server', 'tls_server:wildcard']:
                raise ValueError(f"Invalid cert type: {cert_type}")
            is_wc_domain = cert_type == 'tls_server:wildcard'

        caa_found = False
        valid_for_issue = True

        resource_record_set = None
        while domain != dns.name.root:
            try:
                lookup = dns.resolver.resolve(domain, dns.rdatatype.CAA)
                print(f'Found a CAA record for {domain}! Response: {lookup.rrset.to_text()}')
                resource_record_set = lookup.rrset
                caa_found = True
                break
            except dns.resolver.NoAnswer:
                print(f'No CAA record found for {domain}; trying parent domain...')
                domain = domain.parent()

        # if domain has no CAA records: valid for issuance
        if not caa_found:
            return {
                'statusCode': 200,
                'body': json.dumps({  # TODO rename fields to match API spec, e.g. 'is-valid'
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
        for rr in resource_record_set:
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
                valid_for_issue = MpicCaaChecker.does_value_list_permit_issuance(issue_wild_tags, caa_domains)
            elif len(issue_tags) > 0:
                valid_for_issue = MpicCaaChecker.does_value_list_permit_issuance(issue_tags, caa_domains)
            else:
                # We had no unknown critical tags, and we found no issue tags. Issuance can proceed.
                valid_for_issue = True

        return {
            'statusCode': 200,
            'body': json.dumps({
                'Region': os.environ['AWS_REGION'],
                'ValidForIssue': valid_for_issue,
                'Details': {
                    'Present': True,
                    'FoundAt': domain.to_text(omit_final_dot=True),
                    'Response': resource_record_set.to_text()
                }
            })
        }
