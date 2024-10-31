from open_mpic_core.common_domain.check_parameters import CaaCheckParameters, DcvCheckParameters, \
    DcvDnsGenericValidationDetails, DcvHttpGenericValidationDetails
from open_mpic_core.common_domain.enum.certificate_type import CertificateType
from open_mpic_core.common_domain.enum.dcv_validation_method import DcvValidationMethod
from open_mpic_core.common_domain.enum.dns_record_type import DnsRecordType
from open_mpic_core.mpic_coordinator.domain.mpic_request import BaseMpicRequest
from open_mpic_core.common_domain.enum.check_type import CheckType
from open_mpic_core.mpic_coordinator.domain.mpic_request import MpicCaaRequest
from open_mpic_core.mpic_coordinator.domain.mpic_request import MpicDcvRequest
from open_mpic_core.mpic_coordinator.domain.mpic_request import MpicDcvWithCaaRequest
from open_mpic_core.mpic_coordinator.domain.mpic_orchestration_parameters import MpicRequestOrchestrationParameters


class ValidMpicRequestCreator:
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
                validation_details=ValidMpicRequestCreator.create_validation_details(validation_method)
            )
        )

    @staticmethod
    def create_valid_dcv_with_caa_mpic_request(validation_method=DcvValidationMethod.DNS_GENERIC) -> MpicDcvWithCaaRequest:
        return MpicDcvWithCaaRequest(
            domain_or_ip_target='test',
            orchestration_parameters=MpicRequestOrchestrationParameters(perspective_count=6, quorum_count=4),
            caa_check_parameters=CaaCheckParameters(certificate_type=CertificateType.TLS_SERVER),
            dcv_check_parameters=DcvCheckParameters(
                validation_details=ValidMpicRequestCreator.create_validation_details(validation_method)
            )
        )

    @staticmethod
    def create_valid_mpic_request(check_type: CheckType) -> BaseMpicRequest:
        match check_type:
            case CheckType.CAA:
                return ValidMpicRequestCreator.create_valid_caa_mpic_request()
            case CheckType.DCV:
                return ValidMpicRequestCreator.create_valid_dcv_mpic_request()
            case CheckType.DCV_WITH_CAA:
                return ValidMpicRequestCreator.create_valid_dcv_with_caa_mpic_request()

    @classmethod
    def create_validation_details(cls, validation_method):
        validation_details = {}
        match validation_method:
            case DcvValidationMethod.DNS_GENERIC:
                validation_details = DcvDnsGenericValidationDetails(dns_name_prefix='test', dns_record_type=DnsRecordType.A, challenge_value='test')
            case DcvValidationMethod.HTTP_GENERIC:
                validation_details = DcvHttpGenericValidationDetails(http_token_path='http://example.com', challenge_value='test')  # noqa E501 (http)
        return validation_details
