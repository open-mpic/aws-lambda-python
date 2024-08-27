from aws_lambda_python.common_domain.check_parameters import CaaCheckParameters, DcvCheckParameters, \
    DcvValidationDetails
from aws_lambda_python.common_domain.enum.certificate_type import CertificateType
from aws_lambda_python.common_domain.enum.dcv_validation_method import DcvValidationMethod
from aws_lambda_python.common_domain.enum.dns_record_type import DnsRecordType
from aws_lambda_python.mpic_coordinator.domain.mpic_request import BaseMpicRequest
from aws_lambda_python.common_domain.enum.check_type import CheckType
from aws_lambda_python.mpic_coordinator.domain.mpic_request import MpicCaaRequest
from aws_lambda_python.mpic_coordinator.domain.mpic_request import MpicDcvRequest
from aws_lambda_python.mpic_coordinator.domain.mpic_request import MpicDcvWithCaaRequest
from aws_lambda_python.mpic_coordinator.domain.mpic_orchestration_parameters import MpicRequestOrchestrationParameters


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
        return MpicCaaRequest(
            orchestration_parameters=MpicRequestOrchestrationParameters(domain_or_ip_target='test', perspective_count=6, quorum_count=4),
            caa_check_parameters=CaaCheckParameters(certificate_type=CertificateType.TLS_SERVER)
        )

    @staticmethod
    def create_valid_dcv_check_request(validation_method=DcvValidationMethod.DNS_GENERIC) -> MpicDcvRequest:
        return MpicDcvRequest(
            orchestration_parameters=MpicRequestOrchestrationParameters(domain_or_ip_target='test', perspective_count=6, quorum_count=4),
            dcv_check_parameters=DcvCheckParameters(
                validation_method=validation_method,
                validation_details=ValidRequestCreator.create_validation_details(validation_method)
            )
        )

    @staticmethod
    def create_valid_dcv_with_caa_check_request(validation_method=DcvValidationMethod.DNS_GENERIC) -> MpicDcvWithCaaRequest:
        return MpicDcvWithCaaRequest(
            orchestration_parameters=MpicRequestOrchestrationParameters(domain_or_ip_target='test', perspective_count=6, quorum_count=4),
            caa_check_parameters=CaaCheckParameters(certificate_type=CertificateType.TLS_SERVER),
            dcv_check_parameters=DcvCheckParameters(
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
                validation_details = DcvValidationDetails(challenge_prefix='test', record_type=DnsRecordType.A, expected_challenge='test')
            case DcvValidationMethod.HTTP_GENERIC:
                validation_details = DcvValidationDetails(challenge_path='http://example.com', expected_challenge='test')  # noqa E501 (http)
            case DcvValidationMethod.TLS_USING_ALPN:
                validation_details = DcvValidationDetails(expected_challenge='test')
        return validation_details
