from aws_lambda_python.common_domain.base_check_response import BaseCheckResponse
from pydantic import BaseModel


class CaaCheckResponseDetails(BaseModel):
    present: bool = False
    found_at: str | None = None
    response: str | None = None


class CaaCheckResponse(BaseCheckResponse):
    details: CaaCheckResponseDetails
