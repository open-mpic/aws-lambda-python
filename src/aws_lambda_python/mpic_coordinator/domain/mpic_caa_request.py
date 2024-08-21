from aws_lambda_python.common_domain.certificate_type import CertificateType
from aws_lambda_python.mpic_coordinator.domain.base_mpic_request import BaseMpicRequest
from pydantic import BaseModel


class MpicCaaRequestCaaDetails(BaseModel):
    certificate_type: CertificateType
    caa_domains: list[str] | None = None


class MpicCaaRequest(BaseMpicRequest):
    caa_details: MpicCaaRequestCaaDetails

    @staticmethod
    def from_json(json_string: str) -> 'MpicCaaRequest':
        return MpicCaaRequest.model_validate_json(json_string)
