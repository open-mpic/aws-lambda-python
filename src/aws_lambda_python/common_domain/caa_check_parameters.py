from aws_lambda_python.common_domain.certificate_type import CertificateType
from pydantic import BaseModel


class CaaCheckParameters(BaseModel):
    certificate_type: CertificateType | None = None
    caa_domains: list[str] | None = None
