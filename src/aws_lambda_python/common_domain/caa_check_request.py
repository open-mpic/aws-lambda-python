from aws_lambda_python.common_domain.base_check_request import BaseCheckRequest
from aws_lambda_python.common_domain.caa_check_parameters import CaaCheckParameters


class CaaCheckRequest(BaseCheckRequest):
    domain_or_ip_target: str
    caa_details: CaaCheckParameters | None = None
