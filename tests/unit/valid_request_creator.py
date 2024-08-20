import json

from aws_lambda_python.mpic_coordinator.config.service_config import API_VERSION
from aws_lambda_python.common_domain.certificate_type import CertificateType
from aws_lambda_python.common_domain.dcv_validation_method import DcvValidationMethod
from aws_lambda_python.common_domain.dns_record_type import DnsRecordType
from aws_lambda_python.mpic_coordinator.domain.mpic_request import MpicRequest


class ValidRequestCreator:
    @staticmethod
    def create_valid_caa_check_request_body():
        return {
            'api-version': API_VERSION,
            'system-params': {'domain-or-ip-target': 'test', 'perspective-count': 6, 'quorum-count': 4},
            'caa-details': {'certificate-type': CertificateType.TLS_SERVER}
        }

    @staticmethod
    def create_valid_caa_check_request():
        body = {
            'api-version': API_VERSION,
            'system-params': {'domain-or-ip-target': 'test', 'perspective-count': 6, 'quorum-count': 4},
            'caa-details': {'certificate-type': CertificateType.TLS_SERVER}
        }
        return MpicRequest.from_json(json.dumps(body))

    @staticmethod
    def create_valid_dcv_check_request(validation_method=DcvValidationMethod.DNS_GENERIC):
        body = {
            'api-version': API_VERSION,
            'system-params': {'domain-or-ip-target': 'test', 'perspective-count': 6, 'quorum-count': 4},
            'validation-method': validation_method,
            'validation-details': ValidRequestCreator.create_validation_details(validation_method)
        }
        return MpicRequest.from_json(json.dumps(body))

    @staticmethod
    def create_valid_dcv_with_caa_check_request(validation_method=DcvValidationMethod.DNS_GENERIC):
        body = {
            'api-version': API_VERSION,
            'system-params': {'domain-or-ip-target': 'test', 'perspective-count': 6, 'quorum-count': 4},
            'caa-details': {'certificate-type': CertificateType.TLS_SERVER},
            'validation-method': validation_method,
            'validation-details': ValidRequestCreator.create_validation_details(validation_method)
        }
        return MpicRequest.from_json(json.dumps(body))

    @classmethod
    def create_validation_details(cls, validation_method):
        validation_details = {}
        match validation_method:
            case DcvValidationMethod.DNS_GENERIC:
                validation_details = {'prefix': 'test', 'record-type': DnsRecordType.A, 'expected-challenge': 'test'}
            case DcvValidationMethod.HTTP_GENERIC:
                validation_details = {'path': 'http://example.com', 'expected-challenge': 'test'}  # noqa E501 (http)
            case DcvValidationMethod.TLS_USING_ALPN:
                validation_details = {'expected-challenge': 'test'}
        return validation_details
