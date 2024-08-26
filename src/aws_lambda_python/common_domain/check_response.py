from typing import Union, Literal

from aws_lambda_python.common_domain.validation_error import ValidationError
from aws_lambda_python.common_domain.enum.check_type import CheckType
from pydantic import BaseModel, Field
from typing_extensions import Annotated


class BaseCheckResponse(BaseModel):
    perspective: str
    check_passed: bool = False
    errors: list[ValidationError] | None = None
    # TODO add datetime fields for when the check was made


class CaaCheckResponseDetails(BaseModel):
    caa_record_present: bool = False
    found_at: str | None = None
    response: str | None = None


class CaaCheckResponse(BaseCheckResponse):
    check_type: Literal[CheckType.CAA] = CheckType.CAA
    details: CaaCheckResponseDetails


class DcvCheckResponseDetails(BaseModel):
    http_generic: dict | None = None  # rename? example field 'resolved_ip'
    dns_generic: dict | None = None  # rename?
    # tls-using-alpn?  # TODO add tls-using-alpn?


class DcvCheckResponse(BaseCheckResponse):
    check_type: Literal[CheckType.DCV] = CheckType.DCV
    details: DcvCheckResponseDetails


CheckResponse = Union[CaaCheckResponse, DcvCheckResponse]
AnnotatedCheckResponse = Annotated[CheckResponse, Field(discriminator='check_type')]
