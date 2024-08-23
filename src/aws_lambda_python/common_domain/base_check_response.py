from pydantic import BaseModel


class BaseCheckResponse(BaseModel):
    region: str
    valid_for_issuance: bool = False
