from aws_lambda_python.mpic_coordinator.domain.mpic_caa_request import MpicCaaRequestCaaDetails
from aws_lambda_python.mpic_coordinator.domain.mpic_dcv_request import MpicDcvRequest


class MpicDcvWithCaaRequest(MpicDcvRequest):
    caa_details: MpicCaaRequestCaaDetails

    @staticmethod
    def from_json(json_string: str) -> 'MpicDcvWithCaaRequest':
        return MpicDcvWithCaaRequest.model_validate_json(json_string)
