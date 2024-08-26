from abc import ABC
from pydantic import BaseModel, model_validator

from aws_lambda_python.mpic_coordinator.domain.mpic_orchestration_parameters import MpicRequestOrchestrationParameters
from aws_lambda_python.common_domain.check_parameters import CaaCheckParameters, DcvCheckParameters
from aws_lambda_python.common_domain.enum.dcv_validation_method import DcvValidationMethod


class BaseMpicRequest(BaseModel, ABC):
    api_version: str  # TODO remove when API version in request moves to URL
    orchestration_parameters: MpicRequestOrchestrationParameters

    @model_validator(mode='after')
    def check_perspectives_and_perspective_count_together(self) -> 'BaseMpicRequest':
        assert not (self.orchestration_parameters.perspectives and self.orchestration_parameters.perspective_count), "Request contains both 'perspectives' and 'perspective_count'."
        return self


class MpicCaaRequest(BaseMpicRequest):
    caa_details: CaaCheckParameters


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


class MpicDcvWithCaaRequest(MpicDcvRequest):
    caa_details: CaaCheckParameters
