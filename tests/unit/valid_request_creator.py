from aws_lambda_python.common_domain.caa_check_parameters import CaaCheckParameters
from aws_lambda_python.common_domain.dcv_check_parameters import DcvCheckParameters
from aws_lambda_python.mpic_coordinator.config.service_config import API_VERSION
from aws_lambda_python.common_domain.certificate_type import CertificateType
from aws_lambda_python.common_domain.dcv_validation_method import DcvValidationMethod
from aws_lambda_python.common_domain.dns_record_type import DnsRecordType
from aws_lambda_python.mpic_coordinator.domain.base_mpic_request import BaseMpicRequest
from aws_lambda_python.mpic_coordinator.domain.check_type import CheckType
from aws_lambda_python.mpic_coordinator.domain.mpic_caa_request import MpicCaaRequest
from aws_lambda_python.mpic_coordinator.domain.mpic_dcv_request import MpicDcvRequest
from aws_lambda_python.mpic_coordinator.domain.mpic_dcv_with_caa_request import MpicDcvWithCaaRequest
from aws_lambda_python.mpic_coordinator.domain.mpic_orchestration_parameters import MpicOrchestrationParameters


class ValidRequestCreator:
    @staticmethod
    def create_valid_dcv_check_request_body(validation_method=DcvValidationMethod.DNS_GENERIC):
        request = ValidRequestCreator.create_valid_dcv_check_request(validation_method)
        return request.model_dump()

    @staticmethod
    def create_valid_caa_check_request_body():
        request = ValidRequestCreator.create_valid_caa_check_request()
        return request.model_dump()

    @staticmethod
    def create_valid_dcv_with_caa_check_request_body(validation_method=DcvValidationMethod.DNS_GENERIC):
        request = ValidRequestCreator.create_valid_dcv_with_caa_check_request(validation_method)
        return request.model_dump()

    @staticmethod
    def create_valid_caa_check_request() -> MpicCaaRequest:
        # body = ValidRequestCreator.create_valid_caa_check_request_body()
        # return MpicCaaRequest.from_json(json.dumps(body))
        return MpicCaaRequest(
            api_version=API_VERSION,
            orchestration_parameters=MpicOrchestrationParameters(domain_or_ip_target='test', perspective_count=6, quorum_count=4),
            caa_details=CaaCheckParameters(certificate_type=CertificateType.TLS_SERVER)
        )

    @staticmethod
    def create_valid_dcv_check_request(validation_method=DcvValidationMethod.DNS_GENERIC) -> MpicDcvRequest:
        return MpicDcvRequest(
            api_version=API_VERSION,
            orchestration_parameters=MpicOrchestrationParameters(domain_or_ip_target='test', perspective_count=6, quorum_count=4),
            dcv_details=DcvCheckParameters(
                validation_method=validation_method,
                validation_details=ValidRequestCreator.create_validation_details(validation_method)
            )
        )

    @staticmethod
    def create_valid_dcv_with_caa_check_request(validation_method=DcvValidationMethod.DNS_GENERIC) -> MpicDcvWithCaaRequest:
        return MpicDcvWithCaaRequest(
            api_version=API_VERSION,
            orchestration_parameters=MpicOrchestrationParameters(domain_or_ip_target='test', perspective_count=6, quorum_count=4),
            caa_details=CaaCheckParameters(certificate_type=CertificateType.TLS_SERVER),
            dcv_details=DcvCheckParameters(
                validation_method=validation_method,
                validation_details=ValidRequestCreator.create_validation_details(validation_method)
            )
        )

    @staticmethod
    def create_valid_request(check_type: CheckType) -> BaseMpicRequest:
        match check_type:
            case CheckType.CAA:
                return ValidRequestCreator.create_valid_caa_check_request()
            case CheckType.DCV:
                return ValidRequestCreator.create_valid_dcv_check_request()
            case CheckType.DCV_WITH_CAA:
                return ValidRequestCreator.create_valid_dcv_with_caa_check_request()

    @classmethod
    def create_validation_details(cls, validation_method):
        validation_details = {}
        match validation_method:
            case DcvValidationMethod.DNS_GENERIC:
                validation_details = {'prefix': 'test', 'record_type': DnsRecordType.A, 'expected_challenge': 'test'}
            case DcvValidationMethod.HTTP_GENERIC:
                validation_details = {'path': 'http://example.com', 'expected_challenge': 'test'}  # noqa E501 (http)
            case DcvValidationMethod.TLS_USING_ALPN:
                validation_details = {'expected_challenge': 'test'}
        return validation_details
