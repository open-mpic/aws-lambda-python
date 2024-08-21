from aws_lambda_python.common_domain.dcv_check_parameters import DcvCheckParameters
from aws_lambda_python.common_domain.dcv_validation_method import DcvValidationMethod
from aws_lambda_python.mpic_coordinator.domain.base_mpic_request import BaseMpicRequest
from pydantic import model_validator


class MpicDcvRequest(BaseMpicRequest):
    dcv_details: DcvCheckParameters

    @model_validator(mode='after')
    def check_required_fields_per_validation_method(self) -> 'MpicDcvRequest':
        if self.dcv_details.validation_method == DcvValidationMethod.HTTP_GENERIC:
            assert self.dcv_details.validation_details.path, f"path is required for {DcvValidationMethod.HTTP_GENERIC} validation"
        elif self.dcv_details.validation_method == DcvValidationMethod.DNS_GENERIC:
            assert self.dcv_details.validation_details.record_type, f"record_type is required for {DcvValidationMethod.DNS_GENERIC} validation"
            assert self.dcv_details.validation_details.prefix, f"prefix is required for {DcvValidationMethod.DNS_GENERIC} validation"
        return self

    @staticmethod
    def from_json(json_string: str) -> 'MpicDcvRequest':
        return MpicDcvRequest.model_validate_json(json_string)
