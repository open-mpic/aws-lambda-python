import json

from aws_lambda_python.mpic_coordinator.config.service_config import API_VERSION
from aws_lambda_python.mpic_coordinator.domain.check_type import CheckType
from aws_lambda_python.mpic_coordinator.domain.base_mpic_request import BaseMpicRequest
from aws_lambda_python.mpic_coordinator.domain.mpic_dcv_request import MpicDcvRequest
from aws_lambda_python.mpic_coordinator.domain.mpic_dcv_with_caa_request import MpicDcvWithCaaRequest


# TODO refactor to use a response object instead of a dictionary to avoid magic strings
class MpicResponseBuilder:
    @staticmethod
    def build_response(request: BaseMpicRequest, perspective_count, quorum_count, perspective_responses_per_check_type, valid_by_check_type):
        system_params_as_dict = vars(request.orchestration_parameters)

        response_body = {
            'api_version': API_VERSION,
            'request_system_params': system_params_as_dict,
            'number_of_perspectives_used': perspective_count,
            'required_quorum_count_used': quorum_count,
        }

        # check if request is of type MpicDcvRequest or MpicDcvWithCaaRequest
        if isinstance(request, MpicDcvRequest) or isinstance(request, MpicDcvWithCaaRequest):
            validation_method = request.dcv_details.validation_method
            validation_details_as_dict = vars(request.dcv_details.validation_details)
            response_body['validation_details'] = validation_details_as_dict
            response_body['validation_method'] = validation_method

            if isinstance(request, MpicDcvWithCaaRequest):
                response_body['perspectives_dcv'] = perspective_responses_per_check_type[CheckType.DCV]
                response_body['perspectives_caa'] = perspective_responses_per_check_type[CheckType.CAA]
                response_body['is_valid_dcv'] = valid_by_check_type[CheckType.DCV]
                response_body['is_valid_caa'] = valid_by_check_type[CheckType.CAA]
                response_body['is_valid'] = response_body['is_valid_dcv'] and response_body['is_valid_caa']
            else:
                response_body['perspectives'] = perspective_responses_per_check_type[CheckType.DCV]
                response_body['is_valid'] = valid_by_check_type[CheckType.DCV]
        else:
            response_body['perspectives'] = perspective_responses_per_check_type[CheckType.CAA]
            response_body['is_valid'] = valid_by_check_type[CheckType.CAA]

        return {
            'statusCode': 200,  # other status codes will be returned earlier in the Coordinator logic
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(response_body)
        }
