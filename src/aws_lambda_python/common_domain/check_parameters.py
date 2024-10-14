from abc import ABC
from typing import Literal, Union

from pydantic import BaseModel

from aws_lambda_python.common_domain.enum.certificate_type import CertificateType
from aws_lambda_python.common_domain.enum.dcv_validation_method import DcvValidationMethod
from aws_lambda_python.common_domain.enum.dns_record_type import DnsRecordType


class CaaCheckParameters(BaseModel):
    certificate_type: CertificateType | None = None
    caa_domains: list[str] | None = None


class DcvValidationDetails(BaseModel, ABC):
    validation_method: DcvValidationMethod
    challenge_value: str
    # DNS records have 5 fields: name, ttl, class, type, rdata (which can be multipart itself)
    # A or AAAA: name=domain_name type=A <rdata:address> (ip address)
    # CNAME: name=domain_name_x type=CNAME <rdata:domain_name>
    # TXT: name=domain_name type=TXT <rdata:text> (freeform text)


class DcvHttpGenericValidationDetails(DcvValidationDetails):
    validation_method: Literal[DcvValidationMethod.HTTP_GENERIC] = DcvValidationMethod.HTTP_GENERIC
    http_token_path: str


class DcvDnsGenericValidationDetails(DcvValidationDetails):
    validation_method: Literal[DcvValidationMethod.DNS_GENERIC] = DcvValidationMethod.DNS_GENERIC
    dns_name_prefix: str
    dns_record_type: DnsRecordType


# TODO DcvAcmeValidationDetails


class DcvCheckParameters(BaseModel):
    validation_details: Union[DcvHttpGenericValidationDetails, DcvDnsGenericValidationDetails]
