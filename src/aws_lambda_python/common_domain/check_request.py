from abc import ABC
from pydantic import BaseModel

from aws_lambda_python.common_domain.check_parameters import CaaCheckParameters, DcvCheckParameters


class BaseCheckRequest(BaseModel, ABC):
    domain_or_ip_target: str


class CaaCheckRequest(BaseCheckRequest):
    domain_or_ip_target: str
    caa_check_parameters: CaaCheckParameters | None = None


class DcvCheckRequest(BaseCheckRequest):
    domain_or_ip_target: str
    dcv_check_parameters: DcvCheckParameters

# TODO use an annotated discriminated union
