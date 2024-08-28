import time
from typing import Final
import dns.resolver
import json
import os
import requests

from aws_lambda_python.common_domain.check_request import DcvCheckRequest
from aws_lambda_python.common_domain.check_response import DcvCheckResponse, DcvCheckResponseDetails
from aws_lambda_python.common_domain.enum.dcv_validation_method import DcvValidationMethod
from aws_lambda_python.common_domain.validation_error import ValidationError


# noinspection PyUnusedLocal
class MpicDcvChecker:
    def __init__(self):
        self.default_caa_domain_list = os.environ['default_caa_domains'].split("|")
        self.AWS_REGION: Final[str] = os.environ['AWS_REGION']

    def check_dcv(self, event):
        dcv_request = DcvCheckRequest.model_validate(event)

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
                perspective=self.AWS_REGION,
                check_passed=(result == expected_response_content),
                check_timestamp_ns=time.time_ns(),
                details=DcvCheckResponseDetails(http_generic={'resolved_ip': '0.0.0.0'})  # FIXME get details
            )
        else:
            dcv_check_response = DcvCheckResponse(
                perspective=self.AWS_REGION,
                check_passed=False,
                check_timestamp_ns=time.time_ns(),
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

        print(f"Resolving {dns_record_type.name} record for {name_to_resolve}...")
        try:
            resp = dns.resolver.resolve(name_to_resolve, dns_record_type)
            record_data_as_text = []
            for response_answer in resp.response.answer:
                if response_answer.rdtype == dns_record_type:
                    for record_data in response_answer:
                        record_data_as_text.append(record_data.to_text()[1:-1])  # need to remove enclosing quotes

            dcv_check_response = DcvCheckResponse(
                perspective=self.AWS_REGION,
                check_passed=any([_ == expected_dns_record_content for _ in record_data_as_text]),
                check_timestamp_ns=time.time_ns(),
                details=DcvCheckResponseDetails(dns_generic={'resolved_ip': '0.0.0.0'})  # FIXME get details
            )
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps(dcv_check_response.model_dump())
            }
        except dns.exception.DNSException as e:
            dcv_check_response = DcvCheckResponse(
                perspective=self.AWS_REGION,
                check_passed=False,
                check_timestamp_ns=time.time_ns(),
                errors=[ValidationError(error_type=str(e), error_message=e.msg)],
                details=DcvCheckResponseDetails()
            )
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps(dcv_check_response.model_dump())
            }
