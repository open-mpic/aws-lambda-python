from abc import ABC
from pydantic import BaseModel


class BaseMpicOrchestrationParameters(BaseModel, ABC):
    perspective_count: int | None = None
    quorum_count: int | None = None


class MpicRequestOrchestrationParameters(BaseMpicOrchestrationParameters):
    max_attempts: int | None = None
    perspectives: list[str] | None = None  # for diagnostic purposes


class MpicEffectiveOrchestrationParameters(BaseMpicOrchestrationParameters):
    attempt_count: int | None = 1

