from aws_lambda_python.common_domain.check_parameters import DcvCheckParameters, DcvHttpGenericValidationDetails, \
    DcvDnsGenericValidationDetails
from aws_lambda_python.common_domain.check_request import DcvCheckRequest
from aws_lambda_python.common_domain.enum.dns_record_type import DnsRecordType


class ValidCheckCreator:
    @staticmethod
    def create_valid_http_check_request():
        return DcvCheckRequest(domain_or_ip_target='example.com',
                               dcv_check_parameters=DcvCheckParameters(
                                   validation_details=DcvHttpGenericValidationDetails(
                                       http_token_path='/.well-known/pki_validation/token111_ca1.txt',
                                       challenge_value='challenge_111')
                               ))

    @staticmethod
    def create_valid_dns_check_request(record_type=DnsRecordType.TXT):
        return DcvCheckRequest(domain_or_ip_target='example.com',
                               dcv_check_parameters=DcvCheckParameters(
                                   validation_details=DcvDnsGenericValidationDetails(
                                       dns_name_prefix='_dnsauth',
                                       dns_record_type=record_type,
                                       challenge_value=f"{record_type}_challenge_111.ca1.com.")
                               ))