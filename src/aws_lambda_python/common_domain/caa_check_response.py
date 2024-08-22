from pydantic import BaseModel


class CaaCheckResponseDetails(BaseModel):
    present: bool = False
    found_at: str | None = None
    response: str | None = None


class CaaCheckResponse(BaseModel):
    region: str
    valid_for_issuance: bool = False
    details: CaaCheckResponseDetails
