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
    def create_valid_caa_mpic_request() -> MpicCaaRequest:
        return MpicCaaRequest(
            domain_or_ip_target='test',
            orchestration_parameters=MpicRequestOrchestrationParameters(perspective_count=6, quorum_count=4),
            caa_check_parameters=CaaCheckParameters(certificate_type=CertificateType.TLS_SERVER)
        )

    @staticmethod
    def create_valid_dcv_mpic_request(validation_method=DcvValidationMethod.DNS_GENERIC) -> MpicDcvRequest:
        return MpicDcvRequest(
            domain_or_ip_target='test',
            orchestration_parameters=MpicRequestOrchestrationParameters(perspective_count=6, quorum_count=4),
            dcv_check_parameters=DcvCheckParameters(
                validation_method=validation_method,
                validation_details=ValidRequestCreator.create_validation_details(validation_method)
            )
        )

    @staticmethod
    def create_valid_dcv_with_caa_mpic_request(validation_method=DcvValidationMethod.DNS_GENERIC) -> MpicDcvWithCaaRequest:
        return MpicDcvWithCaaRequest(
            domain_or_ip_target='test',
            orchestration_parameters=MpicRequestOrchestrationParameters(perspective_count=6, quorum_count=4),
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
                return ValidRequestCreator.create_valid_caa_mpic_request()
            case CheckType.DCV:
                return ValidRequestCreator.create_valid_dcv_mpic_request()
            case CheckType.DCV_WITH_CAA:
                return ValidRequestCreator.create_valid_dcv_with_caa_mpic_request()

    @classmethod
    def create_validation_details(cls, validation_method):
        validation_details = {}
        match validation_method:
            case DcvValidationMethod.DNS_GENERIC:
                validation_details = DcvValidationDetails(dns_name_prefix='test', dns_record_type=DnsRecordType.A, challenge_value='test')
            case DcvValidationMethod.HTTP_GENERIC:
                validation_details = DcvValidationDetails(http_token_path='http://example.com', challenge_value='test')  # noqa E501 (http)
            case DcvValidationMethod.TLS_USING_ALPN:
                validation_details = DcvValidationDetails(challenge_value='test')
        return validation_details
