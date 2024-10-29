import json
import os
import time
from typing import Final
import dns.resolver
from dns.name import Name
from dns.rrset import RRset

from aws_lambda_python.common_domain.remote_perspective import RemotePerspective
from aws_lambda_python.common_domain.check_request import CaaCheckRequest
from aws_lambda_python.common_domain.check_response import CaaCheckResponse, CaaCheckResponseDetails
from aws_lambda_python.common_domain.validation_error import ValidationError
from aws_lambda_python.common_domain.enum.certificate_type import CertificateType
from aws_lambda_python.common_domain.messages.ErrorMessages import ErrorMessages

ISSUE_TAG: Final[str] = 'issue'
ISSUEWILD_TAG: Final[str] = 'issuewild'


class MpicCaaLookupException(Exception):  # This is a python exception type used for rase statements.
    pass

class MpicCaaCheckerConfiguration:
    def __init__(self, default_caa_domain_list: list[str], perspective_identity: RemotePerspective):
        self.default_caa_domain_list = default_caa_domain_list
        self.perspective_identity = perspective_identity

class MpicCaaChecker:
    def __init__(self, mpic_caa_checker_configuration: MpicCaaCheckerConfiguration):
        self.default_caa_domain_list = mpic_caa_checker_configuration.default_caa_domain_list
        self.perspective_identity = mpic_caa_checker_configuration.perspective_identity

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
    def find_caa_record_and_domain(caa_request) -> tuple[RRset, Name]:
        rrset = None
        domain = dns.name.from_text(caa_request.domain_or_ip_target)

        while domain != dns.name.root:  # should we stop at TLD / Public Suffix? (e.g., .com, .ac.uk)
            try:
                lookup = dns.resolver.resolve(domain, dns.rdatatype.CAA)
                print(f'Found a CAA record for {domain}! Response: {lookup.rrset.to_text()}')
                rrset = lookup.rrset
                break
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
                print(f'No CAA record found for {domain}; trying parent domain...')
                domain = domain.parent()
            except Exception:
                raise MpicCaaLookupException

        return rrset, domain

    @staticmethod
    def is_valid_for_issuance(caa_domains, is_wc_domain, rrset):
        issue_tags = []
        issue_wild_tags = []
        has_unknown_critical_flags = False

        # Note: a record with critical flag and 'issue' tag will be considered valid for issuance
        for resource_record in rrset:
            tag = resource_record.tag.decode('utf-8')
            tag_lower = tag.lower()
            val = resource_record.value.decode('utf-8')
            if tag_lower == ISSUE_TAG:
                issue_tags.append(val)
            elif tag_lower == ISSUEWILD_TAG:
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

    def check_caa(self, serialized_caa_check_request):
        caa_request = CaaCheckRequest.model_validate(json.loads(serialized_caa_check_request))

        # Assume the default system configured validation targets and override if sent in the API call.
        caa_domains = self.default_caa_domain_list
        is_wc_domain = False
        if caa_request.caa_check_parameters:
            if caa_request.caa_check_parameters.caa_domains:
                caa_domains = caa_request.caa_check_parameters.caa_domains

            # Use the cert type field to check if the domain is a wildcard.
            certificate_type = caa_request.caa_check_parameters.certificate_type
            if certificate_type is not None and certificate_type == CertificateType.TLS_SERVER_WILDCARD:
                is_wc_domain = True

        result = {
            'statusCode': 200,  # note: must be snakeCase
            'headers': {'Content-Type': 'application/json'}
        }

        caa_lookup_error = False
        caa_found = False
        domain = None
        rrset = None
        try:
            rrset, domain = MpicCaaChecker.find_caa_record_and_domain(caa_request)
            caa_found = rrset is not None
        except MpicCaaLookupException:
            caa_lookup_error = True


        #perspective_name = self.rir_region + "." + self.perspective_code

        if caa_lookup_error:
            # TODO would be best to have error types and messages in a separate file to avoid hardcoding strings
            response = CaaCheckResponse(perspective=self.perspective_identity.to_rir_code(), check_passed=False,
                                        errors=[ValidationError(error_type=ErrorMessages.CAA_LOOKUP_ERROR.key, error_message=ErrorMessages.CAA_LOOKUP_ERROR.message)],
                                        details=CaaCheckResponseDetails(caa_record_present=False),  # Possibly should change to present=None to indicate the lookup failed.
                                        timestamp_ns=time.time_ns())
            result['body'] = json.dumps(response.model_dump())
        elif not caa_found:  # if domain has no CAA records: valid for issuance
            response = CaaCheckResponse(perspective=self.perspective_identity.to_rir_code(), check_passed=True,
                                        details=CaaCheckResponseDetails(caa_record_present=False),
                                        timestamp_ns=time.time_ns())
            result['body'] = json.dumps(response.model_dump())
        else:
            valid_for_issuance = MpicCaaChecker.is_valid_for_issuance(caa_domains, is_wc_domain, rrset)
            response = CaaCheckResponse(perspective=self.perspective_identity.to_rir_code(), check_passed=valid_for_issuance,
                                        details=CaaCheckResponseDetails(caa_record_present=True,
                                                                        found_at=domain.to_text(omit_final_dot=True),
                                                                        response=rrset.to_text()),
                                        timestamp_ns=time.time_ns())
            result['body'] = json.dumps(response.model_dump())
        return result
