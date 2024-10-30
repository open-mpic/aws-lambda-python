import json

from open_mpic_core.common_domain.enum.check_type import CheckType
from open_mpic_core.mpic_coordinator.domain.mpic_orchestration_parameters import MpicEffectiveOrchestrationParameters
from open_mpic_core.mpic_coordinator.domain.mpic_request import BaseMpicRequest
from open_mpic_core.mpic_coordinator.domain.mpic_request import MpicDcvRequest
from open_mpic_core.mpic_coordinator.domain.mpic_request import MpicDcvWithCaaRequest
from open_mpic_core.mpic_coordinator.domain.mpic_response import MpicCaaResponse, MpicDcvResponse, MpicDcvWithCaaResponse


class MpicResponseBuilder:
    @staticmethod
    def build_response(request: BaseMpicRequest, perspective_count, quorum_count, attempts, perspective_responses_per_check_type, valid_by_check_type):
        # system_params_as_dict = vars(request.orchestration_parameters)
        actual_orchestration_parameters = MpicEffectiveOrchestrationParameters(
            perspective_count=perspective_count,
            quorum_count=quorum_count,
            attempt_count=attempts
        )

        if type(request) is MpicDcvRequest:  # type() instead of isinstance() because of inheritance
            response_body = MpicDcvResponse(
                request_orchestration_parameters=request.orchestration_parameters,
                actual_orchestration_parameters=actual_orchestration_parameters,
                is_valid=valid_by_check_type[CheckType.DCV],
                perspectives=perspective_responses_per_check_type[CheckType.DCV],
                dcv_check_parameters=request.dcv_check_parameters
            )
        elif type(request) is MpicDcvWithCaaRequest:
            response_body = MpicDcvWithCaaResponse(
                request_orchestration_parameters=request.orchestration_parameters,
                actual_orchestration_parameters=actual_orchestration_parameters,
                is_valid_dcv=valid_by_check_type[CheckType.DCV],
                is_valid_caa=valid_by_check_type[CheckType.CAA],
                is_valid=valid_by_check_type[CheckType.DCV] and valid_by_check_type[CheckType.CAA],
                perspectives_dcv=perspective_responses_per_check_type[CheckType.DCV],
                perspectives_caa=perspective_responses_per_check_type[CheckType.CAA],
                dcv_check_parameters=request.dcv_check_parameters,
                caa_check_parameters=request.caa_check_parameters
            )
        else:
            response_body = MpicCaaResponse(
                request_orchestration_parameters=request.orchestration_parameters,
                actual_orchestration_parameters=actual_orchestration_parameters,
                is_valid=valid_by_check_type[CheckType.CAA],
                perspectives=perspective_responses_per_check_type[CheckType.CAA],
                caa_check_parameters=request.caa_check_parameters
            )

        return {
            'statusCode': 200,  # other status codes returned earlier in Coordinator logic; note: must be snakeCase
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(response_body.model_dump())
        }
