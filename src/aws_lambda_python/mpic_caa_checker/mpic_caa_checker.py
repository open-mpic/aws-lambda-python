import json
import os
from typing import Final

# import dns
import dns.resolver
from aws_lambda_python.common_domain.caa_check_request import CaaCheckRequest
from aws_lambda_python.common_domain.caa_check_response import CaaCheckResponse, CaaCheckResponseDetails
from aws_lambda_python.common_domain.certificate_type import CertificateType
from dns.name import Name
from dns.rrset import RRset

ISSUE_TAG: Final[str] = 'issue'
ISSUEWILD_TAG: Final[str] = 'issuewild'


class MpicCaaChecker:
    def __init__(self):
        self.default_caa_domain_list = os.environ['default_caa_domains'].split("|")
        self.AWS_REGION: Final[str] = os.environ['AWS_REGION']

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

    @staticmethod
    def find_caa_record_and_domain(caa_request) -> (RRset, Name):
        rrset = None
        domain = dns.name.from_text(caa_request.domain_or_ip_target)

        while domain != dns.name.root:
            try:
                lookup = dns.resolver.resolve(domain, dns.rdatatype.CAA)
                print(f'Found a CAA record for {domain}! Response: {lookup.rrset.to_text()}')
                rrset = lookup.rrset
                break
            except dns.resolver.NoAnswer:
                print(f'No CAA record found for {domain}; trying parent domain...')
                domain = domain.parent()

        return rrset, domain

    @staticmethod
    def is_valid_for_issuance(caa_domains, is_wc_domain, rrset):
        # valid_for_issuance = False
        issue_tags = []
        issue_wild_tags = []
        has_unknown_critical_flags = False

        # TODO critical flag behavior is weird...
        # right now a record with critical flag and 'issue' tag will be considered valid for issuance
        for resource_record in rrset:
            tag = resource_record.tag.decode('utf-8')
            val = resource_record.value.decode('utf-8')
            if tag == ISSUE_TAG:
                issue_tags.append(val)
            elif tag == ISSUEWILD_TAG:
                issue_wild_tags.append(val)
            elif resource_record.flags & 0b10000000:  # bitwise-and to check if flags are 128 (the critical flag)
                has_unknown_critical_flags = True

        if has_unknown_critical_flags:
            valid_for_issuance = False
        else:
            if is_wc_domain and len(issue_wild_tags) > 0:
                valid_for_issuance = MpicCaaChecker.does_value_list_permit_issuance(issue_wild_tags, caa_domains)
            elif len(issue_tags) > 0:
                valid_for_issuance = MpicCaaChecker.does_value_list_permit_issuance(issue_tags, caa_domains)
            else:
                # We had no unknown critical tags, and we found no issue tags. Issuance can proceed.
                valid_for_issuance = True
        return valid_for_issuance

    def check_caa(self, event):
        caa_request = CaaCheckRequest.model_validate(event)

        # Assume the default system configured validation targets and override if sent in the API call.
        caa_domains = self.default_caa_domain_list
        is_wc_domain = False
        if caa_request.caa_details:
            if caa_request.caa_details.caa_domains:
                caa_domains = caa_request.caa_details.caa_domains

            # Use the cert type field to check if the domain is a wildcard.
            is_wc_domain = caa_request.caa_details.certificate_type == CertificateType.TLS_SERVER_WILDCARD

        rrset, domain = MpicCaaChecker.find_caa_record_and_domain(caa_request)
        caa_found = rrset is not None

        result = {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'}
        }
        if not caa_found:  # if domain has no CAA records: valid for issuance
            response = CaaCheckResponse(region=self.AWS_REGION, valid_for_issuance=True,
                                        details=CaaCheckResponseDetails(present=False))
            result['body'] = json.dumps(response.model_dump())
        else:
            valid_for_issuance = MpicCaaChecker.is_valid_for_issuance(caa_domains, is_wc_domain, rrset)
            response = CaaCheckResponse(region=self.AWS_REGION, valid_for_issuance=valid_for_issuance,
                                        details=CaaCheckResponseDetails(present=True,
                                                                        found_at=domain.to_text(omit_final_dot=True),
                                                                        response=rrset.to_text()))
            result['body'] = json.dumps(response.model_dump())
        return result
