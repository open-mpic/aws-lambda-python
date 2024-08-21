from aws_lambda_python.common_domain.dcv_validation_method import DcvValidationMethod
from aws_lambda_python.common_domain.dns_record_type import DnsRecordType
from pydantic import BaseModel


class DcvCheckRequestValidationDetails:
    prefix: str | None = None
    record_type: DnsRecordType | None = None
    path: str | None = None
    expected_challenge: str


class DcvCheckRequestDcvDetails(BaseModel):
    validation_method: DcvValidationMethod
    validation_details: DcvCheckRequestValidationDetails


class DcvCheckRequest(BaseModel):
    domain_or_ip_target: str
    dcv_details: DcvCheckRequestDcvDetails
