from pydantic import BaseModel

from aws_lambda_python.common_domain.enum.certificate_type import CertificateType
from aws_lambda_python.common_domain.enum.dcv_validation_method import DcvValidationMethod
from aws_lambda_python.common_domain.enum.dns_record_type import DnsRecordType


class CaaCheckParameters(BaseModel):
    certificate_type: CertificateType | None = None
    caa_domains: list[str] | None = None


class DcvValidationDetails(BaseModel):
    dns_name_prefix: str | None = None
    dns_record_type: DnsRecordType | None = None
    http_token_path: str | None = None
    challenge_value: str
    # DNS records have 5 fields: name, ttl, class, type, rdata (which can be multipart itself)
    # A or AAAA: name=domain_name type=A <rdata:address> (ip address)
    # CNAME: name=domain_name_x type=CNAME <rdata:domain_name>
    # TXT: name=domain_name type=TXT <rdata:text> (freeform text)


class DcvCheckParameters(BaseModel):
    validation_method: DcvValidationMethod
    validation_details: DcvValidationDetails
