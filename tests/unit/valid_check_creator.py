from aws_lambda_python.common_domain.check_parameters import DcvCheckParameters, DcvHttpGenericValidationDetails, \
    DcvDnsGenericValidationDetails, CaaCheckParameters
from aws_lambda_python.common_domain.check_request import DcvCheckRequest, CaaCheckRequest
from aws_lambda_python.common_domain.enum.certificate_type import CertificateType
from aws_lambda_python.common_domain.enum.dns_record_type import DnsRecordType


class ValidCheckCreator:
    @staticmethod
    def create_valid_caa_check_request():
        return CaaCheckRequest(domain_or_ip_target='example.com',
                               caa_check_parameters=CaaCheckParameters(
                                   certificate_type=CertificateType.TLS_SERVER, caa_domains=['ca1.com']
                               ))

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