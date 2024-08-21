from aws_lambda_python.common_domain.caa_check_parameters import CaaCheckParameters
from aws_lambda_python.mpic_coordinator.domain.base_mpic_request import BaseMpicRequest


class MpicCaaRequest(BaseMpicRequest):
    caa_details: CaaCheckParameters

    @staticmethod
    def from_json(json_string: str) -> 'MpicCaaRequest':
        return MpicCaaRequest.model_validate_json(json_string)
