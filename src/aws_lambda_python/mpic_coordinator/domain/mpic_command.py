import json
import re
from dataclasses import dataclass

from aws_lambda_python.common_domain.certificate_type import CertificateType
from aws_lambda_python.common_domain.dcv_validation_method import DcvValidationMethod
from aws_lambda_python.common_domain.dns_record_type import DnsRecordType
from dacite import from_dict, Config
from typing import Optional


@dataclass
class MpicCommand:
    @dataclass
    class MpicCommandSystemParams:
        domain_or_ip_target: Optional[str]
        perspective_count: Optional[int]
        quorum_count: Optional[int]
        perspectives: Optional[list[str]]

    @dataclass
    class MpicCommandCaaDetails:
        certificate_type: Optional[CertificateType]
        caa_domains: Optional[list[str]]

    @dataclass
    class MpicCommandValidationDetails:
        prefix: Optional[str]
        record_type: Optional[DnsRecordType]
        path: Optional[str]
        expected_challenge: Optional[str]

    api_version: Optional[str]  # TODO remove when API version in request moves to URL
    system_params: Optional[MpicCommandSystemParams]
    caa_details: Optional[MpicCommandCaaDetails]
    validation_method: Optional[DcvValidationMethod]
    validation_details: Optional[MpicCommandValidationDetails]

    @staticmethod
    def from_json(json_string: str) -> 'MpicCommand':
        # Convert kebab-case keys to snake_case keys
        # TODO just rework the API to use snake case. This is too hacky, and for what?
        json_with_snake_case_keys = re.sub(r'(-[\w\s"_-]+:)',
                                           lambda matchgroup: matchgroup.group(0).replace('-', '_'),
                                           json_string)
        json_as_dict = json.loads(json_with_snake_case_keys)
        return from_dict(data_class=MpicCommand, data=json_as_dict,
                         config=Config(cast=[CertificateType, DnsRecordType, DcvValidationMethod]))
