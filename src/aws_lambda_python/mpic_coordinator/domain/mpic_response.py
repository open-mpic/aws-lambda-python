from pydantic import BaseModel

from aws_lambda_python.common_domain.check_response import CaaCheckResponse
from aws_lambda_python.mpic_coordinator.domain.mpic_orchestration_parameters import MpicEffectiveOrchestrationParameters
from aws_lambda_python.mpic_coordinator.domain.mpic_orchestration_parameters import MpicRequestOrchestrationParameters
from aws_lambda_python.common_domain.check_parameters import CaaCheckParameters, DcvCheckParameters


class BaseMpicResponse(BaseModel):
    api_version: str
    request_orchestration_parameters: MpicRequestOrchestrationParameters | None = None
    actual_orchestration_parameters: MpicEffectiveOrchestrationParameters | None = None
    is_valid: bool | None = False


class MpicCaaResponse(BaseMpicResponse):
    perspectives: list[str] | None = None  # not set in less verbose mode
    caa_parameters: CaaCheckParameters | None = None  # not set in less verbose mode


class MpicDcvResponse(BaseMpicResponse):
    perspectives: list[str] | None = None  # not set in less verbose mode
    dcv_parameters: DcvCheckParameters | None = None


class MpicDcvWithCaaResponse(BaseMpicResponse):
    perspectives_dcv: list[dict] = None  # TODO define a DcvCheckResponse for the project
    perspectives_caa: list[CaaCheckResponse] = None
    is_valid_dcv: bool | None = False
    is_valid_caa: bool | None = False

