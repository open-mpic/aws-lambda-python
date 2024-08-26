from pydantic import BaseModel


class BaseCheckResponse(BaseModel):
    region: str
    valid_for_issuance: bool = False
    # TODO add datetime fields for when the check was made


class CaaCheckResponseDetails(BaseModel):
    present: bool = False
    found_at: str | None = None
    response: str | None = None
    error: str | None = None


class CaaCheckResponse(BaseCheckResponse):
    details: CaaCheckResponseDetails


class DcvCheckResponseDetails(BaseModel):
    result: str | None = None
    error: str | None = None


class DcvCheckResponse(BaseCheckResponse):
    details: DcvCheckResponseDetails

