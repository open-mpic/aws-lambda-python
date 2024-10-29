import time
from typing import Final
import dns.resolver
import json
import os
import requests

from aws_lambda_python.common_domain.check_request import DcvCheckRequest
from aws_lambda_python.common_domain.check_response import DcvCheckResponse, DcvCheckResponseDetails
from aws_lambda_python.common_domain.enum.dcv_validation_method import DcvValidationMethod
from aws_lambda_python.common_domain.remote_perspective import RemotePerspective
from aws_lambda_python.common_domain.validation_error import ValidationError


class MpicDcvCheckerConfiguration:
    def __init__(self, perspective_identity: RemotePerspective) -> None:
        self.perspective_identity = perspective_identity

# noinspection PyUnusedLocal
class MpicDcvChecker:
    def __init__(self, mpic_dcv_checker_configuration: MpicDcvCheckerConfiguration):
        self.perspective_identity = mpic_dcv_checker_configuration.perspective_identity

    def check_dcv(self, event):
        dcv_request = DcvCheckRequest.model_validate(json.loads(event))

        match dcv_request.dcv_check_parameters.validation_method:
            case DcvValidationMethod.HTTP_GENERIC:
                return self.perform_http_validation(dcv_request)
            case DcvValidationMethod.DNS_GENERIC:
                return self.perform_dns_validation(dcv_request)
            case _:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': 'Unsupported validation method'})
                }

    def perform_http_validation(self, request):
        domain_or_ip_target = request.domain_or_ip_target
        token_path = request.dcv_check_parameters.validation_details.http_token_path
        token_url = f"http://{domain_or_ip_target}/{token_path}"  # noqa E501 (http)
        expected_response_content = request.dcv_check_parameters.validation_details.challenge_value

        response = requests.get(token_url)

        
        if response.status_code == requests.codes.OK:
            result = response.text.strip()
            dcv_check_response = DcvCheckResponse(
                perspective=self.perspective_identity.to_rir_code(),
                check_passed=(result == expected_response_content),
                timestamp_ns=time.time_ns(),
                details=DcvCheckResponseDetails()  # FIXME get details
            )
        else:
            dcv_check_response = DcvCheckResponse(
                perspective=self.perspective_identity.to_rir_code(),
                check_passed=False,
                timestamp_ns=time.time_ns(),
                errors=[ValidationError(error_type=str(response.status_code), error_message=response.reason)],
                details=DcvCheckResponseDetails()
            )

        return {
            'statusCode': response.status_code,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(dcv_check_response.model_dump())
        }

    def perform_dns_validation(self, request):
        
        domain_or_ip_target = request.domain_or_ip_target  # TODO iterate up through parent domains to base domain?
        dns_name_prefix = request.dcv_check_parameters.validation_details.dns_name_prefix
        dns_record_type = dns.rdatatype.from_text(request.dcv_check_parameters.validation_details.dns_record_type)
        if dns_name_prefix is not None and len(dns_name_prefix) > 0:
            name_to_resolve = f"{dns_name_prefix}.{domain_or_ip_target}"
        else:
            name_to_resolve = domain_or_ip_target
        expected_dns_record_content = request.dcv_check_parameters.validation_details.challenge_value

        # TODO add leading underscore to name_to_resolve if it's not found?

        print(f"Resolving {dns_record_type.name} record for {name_to_resolve}...")
        try:
            lookup = dns.resolver.resolve(name_to_resolve, dns_record_type)
            records_as_strings = []
            for response_answer in lookup.response.answer:
                if response_answer.rdtype == dns_record_type:
                    for record_data in response_answer:
                        # only need to remove enclosing quotes if they're there, e.g., for a TXT record
                        record_data_as_string = record_data.to_text()
                        if record_data_as_string[0] == '"' and record_data_as_string[-1] == '"':
                            records_as_strings.append(record_data_as_string[1:-1])
                        else:
                            records_as_strings.append(record_data_as_string)

            dcv_check_response = DcvCheckResponse(
                perspective=self.perspective_identity.to_rir_code(),
                check_passed=expected_dns_record_content in records_as_strings,
                timestamp_ns=time.time_ns(),
                details=DcvCheckResponseDetails()  # FIXME get details (or don't bother with this)
            )
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps(dcv_check_response.model_dump())
            }
        except dns.exception.DNSException as e:
            dcv_check_response = DcvCheckResponse(
                perspective=self.perspective_identity.to_rir_code(),
                check_passed=False,
                timestamp_ns=time.time_ns(),
                errors=[ValidationError(error_type=e.__class__.__name__, error_message=e.msg)],
                details=DcvCheckResponseDetails()
            )
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps(dcv_check_response.model_dump())
            }
