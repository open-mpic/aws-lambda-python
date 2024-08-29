from abc import ABC
from typing import Literal

from aws_lambda_python.common_domain.enum.check_type import CheckType
from pydantic import BaseModel, model_validator

from aws_lambda_python.mpic_coordinator.domain.mpic_orchestration_parameters import MpicRequestOrchestrationParameters
from aws_lambda_python.common_domain.check_parameters import CaaCheckParameters, DcvCheckParameters
from aws_lambda_python.common_domain.enum.dcv_validation_method import DcvValidationMethod


class BaseMpicRequest(BaseModel, ABC):
    domain_or_ip_target: str
    check_type: CheckType
    orchestration_parameters: MpicRequestOrchestrationParameters | None = None

    @model_validator(mode='after')
    def check_perspectives_and_perspective_count_together(self) -> 'BaseMpicRequest':
        if self.orchestration_parameters:
            assert not (self.orchestration_parameters.perspectives and self.orchestration_parameters.perspective_count), "Request contains both 'perspectives' and 'perspective_count'."
        return self


class MpicCaaRequest(BaseMpicRequest):
    check_type: Literal[CheckType.CAA] = CheckType.CAA
    caa_check_parameters: CaaCheckParameters | None = None


class MpicDcvRequest(BaseMpicRequest):
    check_type: Literal[CheckType.DCV] = CheckType.DCV
    dcv_check_parameters: DcvCheckParameters

    @model_validator(mode='after')
    def check_required_fields_per_validation_method(self) -> 'MpicDcvRequest':
        if self.dcv_check_parameters.validation_method == DcvValidationMethod.HTTP_GENERIC:
            assert self.dcv_check_parameters.validation_details.http_token_path, f"http_token_path is required for {DcvValidationMethod.HTTP_GENERIC} validation"
        elif self.dcv_check_parameters.validation_method == DcvValidationMethod.DNS_GENERIC:
            assert self.dcv_check_parameters.validation_details.dns_record_type, f"dns_record_type is required for {DcvValidationMethod.DNS_GENERIC} validation"
            assert self.dcv_check_parameters.validation_details.dns_name_prefix, f"dns_name_prefix is required for {DcvValidationMethod.DNS_GENERIC} validation"
        return self


class MpicDcvWithCaaRequest(MpicDcvRequest):  # inherits from MpicDcvRequest rather than BaseMpicRequest
    check_type: Literal[CheckType.DCV_WITH_CAA] = CheckType.DCV_WITH_CAA
    caa_check_parameters: CaaCheckParameters

# TODO use an annotated discriminated union
