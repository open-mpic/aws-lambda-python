from pydantic import BaseModel

from aws_lambda_python.common_domain.enum.certificate_type import CertificateType
from aws_lambda_python.common_domain.enum.dcv_validation_method import DcvValidationMethod
from aws_lambda_python.common_domain.enum.dns_record_type import DnsRecordType


class CaaCheckParameters(BaseModel):
    certificate_type: CertificateType | None = None
    caa_domains: list[str] | None = None


class DcvValidationDetails(BaseModel):
    prefix: str | None = None
    record_type: DnsRecordType | None = None
    path: str | None = None
    expected_challenge: str


class DcvCheckParameters(BaseModel):
    validation_method: DcvValidationMethod
    validation_details: DcvValidationDetails
