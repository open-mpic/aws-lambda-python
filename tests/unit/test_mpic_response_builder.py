import json
import pytest

from aws_lambda_python.mpic_coordinator.config.service_config import API_VERSION
from aws_lambda_python.mpic_coordinator.domain.check_type import CheckType
from aws_lambda_python.mpic_coordinator.domain.request_path import RequestPath
from aws_lambda_python.mpic_coordinator.mpic_response_builder import MpicResponseBuilder
from valid_request_creator import ValidRequestCreator


class TestMpicResponseBuilder:
    @staticmethod
    def create_perspective_responses_per_check_type(request_path=RequestPath.DCV_WITH_CAA_CHECK):
        responses = {}
        caa_responses = [  # 1 false
                    {'perspective': 'p1', 'is-valid': True},
                    {'perspective': 'p2', 'is-valid': False},
                    {'perspective': 'p3', 'is-valid': True},
                    {'perspective': 'p4', 'is-valid': True},
                    {'perspective': 'p5', 'is-valid': True},
                    {'perspective': 'p6', 'is-valid': True}
                ]
        dcv_responses = [  # 2 false
                {'perspective': 'p1', 'is-valid': True},
                {'perspective': 'p2', 'is-valid': True},
                {'perspective': 'p3', 'is-valid': True},
                {'perspective': 'p4', 'is-valid': True},
                {'perspective': 'p5', 'is-valid': False},
                {'perspective': 'p6', 'is-valid': False}
            ]

        match request_path:
            case RequestPath.CAA_CHECK:
                responses[CheckType.CAA] = caa_responses
            case RequestPath.DCV_CHECK:
                responses[CheckType.DCV] = dcv_responses
            case RequestPath.DCV_WITH_CAA_CHECK:
                responses[CheckType.CAA] = caa_responses
                responses[CheckType.DCV] = dcv_responses

        return responses

    @staticmethod
    def create_validity_by_check_type(request_path=RequestPath.DCV_WITH_CAA_CHECK):
        validity_by_check_type = {}
        match request_path:
            case RequestPath.CAA_CHECK:
                validity_by_check_type[CheckType.CAA] = True
            case RequestPath.DCV_CHECK:
                validity_by_check_type[CheckType.DCV] = False
            case RequestPath.DCV_WITH_CAA_CHECK:
                validity_by_check_type[CheckType.CAA] = True
                validity_by_check_type[CheckType.DCV] = True
        return validity_by_check_type

    @pytest.mark.parametrize('request_path, perspective_count, quorum_count', [
        (RequestPath.CAA_CHECK, 6, 4),
        (RequestPath.DCV_CHECK, 6, 5),  # higher quorum count
        (RequestPath.DCV_WITH_CAA_CHECK, 6, 4)
    ])
    def build_response__should_return_response_given_mpic_request_configuration_and_results(self, request_path, perspective_count, quorum_count):
        persp_responses_per_check_type = self.create_perspective_responses_per_check_type(request_path)
        valid_by_check_type = self.create_validity_by_check_type(request_path)
        command = ValidRequestCreator.create_valid_caa_check_command()  # check type doesn't matter in this case
        response = MpicResponseBuilder.build_response(request_path, command, perspective_count, quorum_count, persp_responses_per_check_type, valid_by_check_type)
        assert response['statusCode'] == 200
        response_body = json.loads(response['body'])
        assert response_body['api-version'] == API_VERSION
        assert response_body['request-system-params']['perspective_count'] == command.system_params.perspective_count
        assert response_body['number-of-perspectives-used'] == perspective_count
        assert response_body['required-quorum-count-used'] == quorum_count
        match request_path:
            case RequestPath.CAA_CHECK:
                assert response_body['perspectives'] == persp_responses_per_check_type[CheckType.CAA]
                assert response_body['is-valid'] == valid_by_check_type[CheckType.CAA]
            case RequestPath.DCV_CHECK:
                assert response_body['perspectives'] == persp_responses_per_check_type[CheckType.DCV]
                assert response_body['is-valid'] == valid_by_check_type[CheckType.DCV]
            case RequestPath.DCV_WITH_CAA_CHECK:
                assert response_body['perspectives-dcv'] == persp_responses_per_check_type[CheckType.DCV]
                assert response_body['perspectives-caa'] == persp_responses_per_check_type[CheckType.CAA]
                assert response_body['is-valid-dcv'] == valid_by_check_type[CheckType.DCV]
                assert response_body['is-valid-caa'] == valid_by_check_type[CheckType.CAA]
                assert response_body['is-valid'] == response_body['is-valid-dcv'] and response_body['is-valid-caa']

    def build_response__should_include_validation_details_and_method_when_present_in_request_body(self):
        command = ValidRequestCreator.create_valid_dcv_check_command()
        request_path = RequestPath.DCV_CHECK
        persp_responses_per_check_type = self.create_perspective_responses_per_check_type(RequestPath.DCV_CHECK)
        valid_by_check_type = self.create_validity_by_check_type(RequestPath.DCV_CHECK)
        response = MpicResponseBuilder.build_response(request_path, command, 6, 5, persp_responses_per_check_type, valid_by_check_type)
        response_body = json.loads(response['body'])
        assert response_body['validation-details']['expected_challenge'] == command.validation_details.expected_challenge
        assert response_body['validation-method'] == command.validation_method

    def build_response__should_set_is_valid_to_false_when_either_check_type_is_invalid(self):
        command = ValidRequestCreator.create_valid_dcv_with_caa_check_command()
        request_path = RequestPath.DCV_WITH_CAA_CHECK
        persp_responses_per_check_type = self.create_perspective_responses_per_check_type(RequestPath.DCV_WITH_CAA_CHECK)
        valid_by_check_type = self.create_validity_by_check_type(RequestPath.DCV_WITH_CAA_CHECK)
        valid_by_check_type[CheckType.DCV] = False
        response = MpicResponseBuilder.build_response(request_path, command, 6, 4, persp_responses_per_check_type, valid_by_check_type)
        response_body = json.loads(response['body'])
        assert response_body['is-valid'] is False


if __name__ == '__main__':
    pytest.main()
