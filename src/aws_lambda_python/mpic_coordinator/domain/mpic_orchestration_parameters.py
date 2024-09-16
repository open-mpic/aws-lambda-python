from abc import ABC
from pydantic import BaseModel


class BaseMpicOrchestrationParameters(BaseModel, ABC):
    perspective_count: int
    quorum_count: int


class MpicRequestOrchestrationParameters(BaseMpicOrchestrationParameters):
    max_attempts: int | None = 1
    perspectives: list[str] | None = None  # for diagnostic purposes


class MpicEffectiveOrchestrationParameters(BaseMpicOrchestrationParameters):
    attempt_count: int | None = 1

