from aws_lambda_python.common_domain.caa_check_parameters import CaaCheckParameters
from aws_lambda_python.mpic_coordinator.domain.mpic_dcv_request import MpicDcvRequest


class MpicDcvWithCaaRequest(MpicDcvRequest):
    caa_details: CaaCheckParameters

    @staticmethod
    def from_json(json_string: str) -> 'MpicDcvWithCaaRequest':
        return MpicDcvWithCaaRequest.model_validate_json(json_string)
