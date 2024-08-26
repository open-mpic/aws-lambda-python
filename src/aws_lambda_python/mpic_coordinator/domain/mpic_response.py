from abc import ABC
from typing import Union, Literal

from aws_lambda_python.common_domain.enum.check_type import CheckType
from pydantic import BaseModel, Field

from aws_lambda_python.common_domain.check_response import CaaCheckResponse, DcvCheckResponse
from aws_lambda_python.mpic_coordinator.domain.mpic_orchestration_parameters import MpicEffectiveOrchestrationParameters
from aws_lambda_python.mpic_coordinator.domain.mpic_orchestration_parameters import MpicRequestOrchestrationParameters
from aws_lambda_python.common_domain.check_parameters import CaaCheckParameters, DcvCheckParameters
from typing_extensions import Annotated


class BaseMpicResponse(BaseModel, ABC):
    request_orchestration_parameters: MpicRequestOrchestrationParameters | None = None
    actual_orchestration_parameters: MpicEffectiveOrchestrationParameters | None = None
    is_valid: bool | None = False


class MpicCaaResponse(BaseMpicResponse):
    check_type: Literal[CheckType.CAA] = CheckType.CAA
    perspectives: list[CaaCheckResponse] | None = None  # not set in less verbose mode
    caa_parameters: CaaCheckParameters | None = None  # not set in less verbose mode


class MpicDcvResponse(BaseMpicResponse):
    check_type: Literal[CheckType.DCV] = CheckType.DCV
    perspectives: list[DcvCheckResponse] | None = None  # not set in less verbose mode
    dcv_parameters: DcvCheckParameters | None = None


class MpicDcvWithCaaResponse(BaseMpicResponse):
    check_type: Literal[CheckType.DCV_WITH_CAA] = CheckType.DCV_WITH_CAA
    perspectives_dcv: list[DcvCheckResponse] = None  # TODO define a DcvCheckResponse for the project
    perspectives_caa: list[CaaCheckResponse] = None
    is_valid_dcv: bool | None = False
    is_valid_caa: bool | None = False


MpicResponse = Union[MpicCaaResponse, MpicDcvResponse, MpicDcvWithCaaResponse]
AnnotatedMpicResponse = Annotated[MpicResponse, Field(discriminator='check_type')]
