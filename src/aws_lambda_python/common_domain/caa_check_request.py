from aws_lambda_python.common_domain.certificate_type import CertificateType
from pydantic import BaseModel


class CaaCheckRequestCaaDetails(BaseModel):
    certificate_type: CertificateType | None = None
    caa_domains: list[str] | None = None


class CaaCheckRequest(BaseModel):
    domain_or_ip_target: str
    caa_details: CaaCheckRequestCaaDetails | None = None
