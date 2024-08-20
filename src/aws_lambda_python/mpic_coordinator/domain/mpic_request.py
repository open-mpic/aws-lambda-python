import json
import re
from dataclasses import dataclass

from aws_lambda_python.common_domain.certificate_type import CertificateType
from aws_lambda_python.common_domain.dcv_validation_method import DcvValidationMethod
from aws_lambda_python.common_domain.dns_record_type import DnsRecordType
from dacite import from_dict, Config
from typing import Optional
from pydantic import BaseModel


@dataclass
class MpicRequest(BaseModel):
    @dataclass
    class MpicRequestSystemParams(BaseModel):
        domain_or_ip_target: Optional[str] = None
        perspective_count: Optional[int] = None
        quorum_count: Optional[int] = None
        perspectives: Optional[list[str]] = None

    @dataclass
    class MpicRequestCaaDetails(BaseModel):
        certificate_type: Optional[CertificateType] = None
        caa_domains: Optional[list[str]] = None

    @dataclass
    class MpicRequestValidationDetails(BaseModel):
        prefix: Optional[str] = None
        record_type: Optional[DnsRecordType] = None
        path: Optional[str] = None
        expected_challenge: Optional[str] = None

    api_version: Optional[str] = None  # TODO remove when API version in request moves to URL
    system_params: Optional[MpicRequestSystemParams] = None
    caa_details: Optional[MpicRequestCaaDetails] = None
    validation_method: Optional[DcvValidationMethod] = None
    validation_details: Optional[MpicRequestValidationDetails] = None

    @staticmethod
    def from_json(json_string: str) -> 'MpicRequest':
        json_with_snake_case_keys = re.sub(r'(-[\w\s"_-]+:)',
                                           lambda matchgroup: matchgroup.group(0).replace('-', '_'),
                                           json_string)
        return MpicRequest.model_validate_json(json_with_snake_case_keys)
