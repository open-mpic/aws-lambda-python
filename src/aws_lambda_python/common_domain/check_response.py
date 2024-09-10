from typing import Union, Literal

from aws_lambda_python.common_domain.errors import ValidationError
from aws_lambda_python.common_domain.enum.check_type import CheckType
from pydantic import BaseModel, Field
from typing_extensions import Annotated


class BaseCheckResponse(BaseModel):
    perspective: str
    check_passed: bool = False
    errors: list[ValidationError] | None = None
    timestamp_ns: int | None = None  # TODO what do we name this field?


class CaaCheckResponseDetails(BaseModel):
    caa_record_present: bool = False  # TODO allow None to reflect potential error state
    found_at: str | None = None
    response: str | None = None


class CaaCheckResponse(BaseCheckResponse):
    check_type: Literal[CheckType.CAA] = CheckType.CAA
    details: CaaCheckResponseDetails


class DcvCheckResponseDetails(BaseModel):
    http_generic: dict | None = None  # rename?
    dns_generic: dict | None = None  # rename?
    # FIXME probably need to define details instead of just a dict


class DcvCheckResponse(BaseCheckResponse):
    check_type: Literal[CheckType.DCV] = CheckType.DCV
    details: DcvCheckResponseDetails


CheckResponse = Union[CaaCheckResponse, DcvCheckResponse]
AnnotatedCheckResponse = Annotated[CheckResponse, Field(discriminator='check_type')]
