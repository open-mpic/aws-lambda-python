from pydantic import BaseModel


class MpicOrchestrationParameters(BaseModel):
    domain_or_ip_target: str
    perspective_count: int | None = None
    quorum_count: int | None = None
    perspectives: list[str] | None = None
    max_attempts: int | None = None
