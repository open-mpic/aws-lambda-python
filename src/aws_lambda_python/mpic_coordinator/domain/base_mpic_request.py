from abc import ABC

from pydantic import BaseModel, model_validator


class MpicRequestSystemParams(BaseModel):
    domain_or_ip_target: str
    perspective_count: int | None = None
    quorum_count: int | None = None
    perspectives: list[str] | None = None


class BaseMpicRequest(BaseModel, ABC):
    api_version: str  # TODO remove when API version in request moves to URL
    system_params: MpicRequestSystemParams

    @model_validator(mode='after')
    def check_perspectives_and_perspective_count_together(self) -> 'BaseMpicRequest':
        assert not (self.system_params.perspectives and self.system_params.perspective_count), "Request contains both 'perspectives' and 'perspective_count'."
        return self
