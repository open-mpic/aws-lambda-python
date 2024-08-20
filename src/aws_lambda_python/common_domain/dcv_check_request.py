from dataclasses import dataclass
from typing import Optional

from aws_lambda_python.common_domain.dcv_validation_method import DcvValidationMethod
from aws_lambda_python.common_domain.dns_record_type import DnsRecordType


@dataclass
class DcvCheckRequest:
    @dataclass
    class DcvCheckRequestValidationDetails:
        prefix: Optional[str]
        record_type: Optional[DnsRecordType]
        path: Optional[str]
        expected_challenge: str

    domain_or_ip_target: str
    validation_method: DcvValidationMethod
    validation_details: Optional[DcvCheckRequestValidationDetails]
