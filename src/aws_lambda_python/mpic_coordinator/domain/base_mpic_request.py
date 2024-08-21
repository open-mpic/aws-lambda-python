from abc import ABC
from pydantic import BaseModel, model_validator

from aws_lambda_python.mpic_coordinator.domain.mpic_orchestration_parameters import MpicOrchestrationParameters


class BaseMpicRequest(BaseModel, ABC):
    api_version: str  # TODO remove when API version in request moves to URL
    orchestration_parameters: MpicOrchestrationParameters

    @model_validator(mode='after')
    def check_perspectives_and_perspective_count_together(self) -> 'BaseMpicRequest':
        assert not (self.orchestration_parameters.perspectives and self.orchestration_parameters.perspective_count), "Request contains both 'perspectives' and 'perspective_count'."
        return self
