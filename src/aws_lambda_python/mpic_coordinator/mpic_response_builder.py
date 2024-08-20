import json

from aws_lambda_python.mpic_coordinator.config.service_config import API_VERSION
from aws_lambda_python.mpic_coordinator.domain.check_type import CheckType
from aws_lambda_python.mpic_coordinator.domain.mpic_command import MpicCommand
from aws_lambda_python.mpic_coordinator.domain.request_path import RequestPath


# TODO refactor to use dataclasses once API is updated to use snake care instead of kebab case for attribute names
class MpicResponseBuilder:
    @staticmethod
    def build_response(request_path, request_command: MpicCommand, perspective_count, quorum_count, perspective_responses_per_check_type, valid_by_check_type):
        system_params = request_command.system_params if request_command.system_params else None
        validation_details = request_command.validation_details if request_command.validation_details else None
        validation_method = request_command.validation_method if request_command.validation_method else None
        system_params_as_dict = vars(system_params) if system_params else None
        validation_details_as_dict = vars(validation_details) if validation_details else None

        response_body = {
            'api-version': API_VERSION,
            'request-system-params': system_params_as_dict,
            'number-of-perspectives-used': perspective_count,
            'required-quorum-count-used': quorum_count,
        }

        match request_path:
            case RequestPath.CAA_CHECK:
                response_body['perspectives'] = perspective_responses_per_check_type[CheckType.CAA]
                response_body['is-valid'] = valid_by_check_type[CheckType.CAA]
            case RequestPath.DCV_CHECK:
                response_body['perspectives'] = perspective_responses_per_check_type[CheckType.DCV]
                response_body['validation-details'] = validation_details_as_dict
                response_body['validation-method'] = validation_method
                response_body['is-valid'] = valid_by_check_type[CheckType.DCV]
            case RequestPath.DCV_WITH_CAA_CHECK:
                response_body['perspectives-dcv'] = perspective_responses_per_check_type[CheckType.DCV]
                response_body['perspectives-caa'] = perspective_responses_per_check_type[CheckType.CAA]
                response_body['validation-details'] = validation_details_as_dict
                response_body['validation-method'] = validation_method
                response_body['is-valid-dcv'] = valid_by_check_type[CheckType.DCV]
                response_body['is-valid-caa'] = valid_by_check_type[CheckType.CAA]
                response_body['is-valid'] = response_body['is-valid-dcv'] and response_body['is-valid-caa']

        return {
            'statusCode': 200,  # other status codes will be returned earlier in the Coordinator logic
            'body': json.dumps(response_body)
        }
