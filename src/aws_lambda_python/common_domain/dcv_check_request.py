from aws_lambda_python.common_domain.base_check_request import BaseCheckRequest
from aws_lambda_python.common_domain.dcv_check_parameters import DcvCheckParameters


class DcvCheckRequest(BaseCheckRequest):
    domain_or_ip_target: str
    dcv_details: DcvCheckParameters
