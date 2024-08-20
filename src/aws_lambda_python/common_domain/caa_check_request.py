from dataclasses import dataclass
from typing import Optional

from aws_lambda_python.common_domain.certificate_type import CertificateType


@dataclass
class CaaCheckRequest:
    domain_or_ip_target: str
    certificate_type: CertificateType
    caa_domains: Optional[list[str]]
