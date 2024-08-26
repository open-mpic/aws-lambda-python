import json

from aws_lambda_python.mpic_coordinator.config.service_config import API_VERSION
from aws_lambda_python.mpic_coordinator.domain.enum.check_type import CheckType
from aws_lambda_python.mpic_coordinator.domain.mpic_orchestration_parameters import MpicEffectiveOrchestrationParameters
from aws_lambda_python.mpic_coordinator.domain.mpic_request import BaseMpicRequest
from aws_lambda_python.mpic_coordinator.domain.mpic_request import MpicDcvRequest
from aws_lambda_python.mpic_coordinator.domain.mpic_request import MpicDcvWithCaaRequest
from aws_lambda_python.mpic_coordinator.domain.mpic_response import MpicCaaResponse, MpicDcvResponse, MpicDcvWithCaaResponse


class MpicResponseBuilder:
    @staticmethod
    def build_response(request: BaseMpicRequest, perspective_count, quorum_count, perspective_responses_per_check_type, valid_by_check_type):
        # system_params_as_dict = vars(request.orchestration_parameters)
        actual_orchestration_parameters = MpicEffectiveOrchestrationParameters(
            perspective_count=perspective_count,
            quorum_count=quorum_count,
            attempt_count=1  # TODO implement retry logic
        )

        if type(request) is MpicDcvRequest:  # type() instead of isinstance() because of inheritance
            response_body = MpicDcvResponse(
                api_version=API_VERSION,
                request_orchestration_parameters=request.orchestration_parameters,
                actual_orchestration_parameters=actual_orchestration_parameters,
                is_valid=valid_by_check_type[CheckType.DCV],
                perspectives=perspective_responses_per_check_type[CheckType.DCV],
                dcv_parameters=request.dcv_check_parameters
            )
        elif type(request) is MpicDcvWithCaaRequest:
            response_body = MpicDcvWithCaaResponse(
                api_version=API_VERSION,
                request_orchestration_parameters=request.orchestration_parameters,
                actual_orchestration_parameters=actual_orchestration_parameters,
                is_valid_dcv=valid_by_check_type[CheckType.DCV],
                is_valid_caa=valid_by_check_type[CheckType.CAA],
                is_valid=valid_by_check_type[CheckType.DCV] and valid_by_check_type[CheckType.CAA],
                perspectives_dcv=perspective_responses_per_check_type[CheckType.DCV],
                perspectives_caa=perspective_responses_per_check_type[CheckType.CAA],
                dcv_parameters=request.dcv_check_parameters,
                caa_parameters=request.caa_check_parameters
            )
        else:
            response_body = MpicCaaResponse(
                api_version=API_VERSION,
                request_orchestration_parameters=request.orchestration_parameters,
                actual_orchestration_parameters=actual_orchestration_parameters,
                is_valid=valid_by_check_type[CheckType.CAA],
                perspectives=perspective_responses_per_check_type[CheckType.CAA],
                caa_parameters=request.caa_check_parameters
            )

        # response_body = {
        #     'api_version': API_VERSION,
        #     'request_system_params': system_params_as_dict,
        #     'number_of_perspectives_used': perspective_count,
        #     'required_quorum_count_used': quorum_count,
        # }
        #
        # # check if request is of type MpicDcvRequest or MpicDcvWithCaaRequest
        # if isinstance(request, MpicDcvRequest) or isinstance(request, MpicDcvWithCaaRequest):
        #     validation_method = request.dcv_check_parameters.validation_method
        #     validation_details_as_dict = vars(request.dcv_check_parameters.validation_details)
        #     response_body['validation_details'] = validation_details_as_dict
        #     response_body['validation_method'] = validation_method
        #
        #     if isinstance(request, MpicDcvWithCaaRequest):
        #         response_body['perspectives_dcv'] = perspective_responses_per_check_type[CheckType.DCV]
        #         response_body['perspectives_caa'] = perspective_responses_per_check_type[CheckType.CAA]
        #         response_body['is_valid_dcv'] = valid_by_check_type[CheckType.DCV]
        #         response_body['is_valid_caa'] = valid_by_check_type[CheckType.CAA]
        #         response_body['is_valid'] = response_body['is_valid_dcv'] and response_body['is_valid_caa']
        #     else:
        #         response_body['perspectives'] = perspective_responses_per_check_type[CheckType.DCV]
        #         response_body['is_valid'] = valid_by_check_type[CheckType.DCV]
        # else:
        #     response_body['perspectives'] = perspective_responses_per_check_type[CheckType.CAA]
        #     response_body['is_valid'] = valid_by_check_type[CheckType.CAA]

        # return {
        #     'statusCode': 200,  # other status codes returned earlier in Coordinator logic; note: must be snakeCase
        #     'headers': {'Content-Type': 'application/json'},
        #     'body': json.dumps(response_body)
        # }
        return {
            'statusCode': 200,  # other status codes returned earlier in Coordinator logic; note: must be snakeCase
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(response_body.model_dump())
        }