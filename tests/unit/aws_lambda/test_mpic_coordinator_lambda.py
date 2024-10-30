import io
import json

import pytest

from open_mpic_core.common_domain.check_request import DcvCheckRequest
from open_mpic_core.common_domain.check_response import DcvCheckResponse, DcvCheckResponseDetails
from open_mpic_core.common_domain.enum.check_type import CheckType
from open_mpic_core.common_domain.remote_perspective import RemotePerspective
from open_mpic_core.mpic_coordinator.domain.enum.request_path import RequestPath
from open_mpic_core.mpic_coordinator.domain.mpic_orchestration_parameters import MpicEffectiveOrchestrationParameters
from open_mpic_core.mpic_coordinator.domain.mpic_response import MpicCaaResponse
from aws_lambda_mpic.mpic_coordinator_lambda.mpic_coordinator_lambda_function import MpicCoordinatorLambdaHandler
from botocore.response import StreamingBody
import aws_lambda_mpic.mpic_coordinator_lambda.mpic_coordinator_lambda_function as mpic_coordinator_lambda_function

from unit.valid_check_creator import ValidCheckCreator
from unit.valid_mpic_request_creator import ValidMpicRequestCreator


class TestMpicCoordinatorLambda:
    @staticmethod
    @pytest.fixture(scope='class')
    def set_env_variables():
        envvars = {
            'perspective_names': 'arin.us-east-1|arin.us-west-1|ripe.eu-west-2|ripe.eu-central-2|apnic.ap-northeast-1|apnic.ap-south-2',
            'validator_arns': 'arn:aws:acm-pca:us-east-1:123456789012:validator/arin.us-east-1|arn:aws:acm-pca:us-west-1:123456789012:validator/arin.us-west-1|arn:aws:acm-pca:eu-west-2:123456789012:validator/ripe.eu-west-2|arn:aws:acm-pca:eu-central-2:123456789012:validator/ripe.eu-central-2|arn:aws:acm-pca:ap-northeast-1:123456789012:validator/apnic.ap-northeast-1|arn:aws:acm-pca:ap-south-2:123456789012:validator/apnic.ap-south-2',
            'caa_arns': 'arn:aws:acm-pca:us-east-1:123456789012:caa/arin.us-east-1|arn:aws:acm-pca:us-west-1:123456789012:caa/arin.us-west-1|arn:aws:acm-pca:eu-west-2:123456789012:caa/ripe.eu-west-2|arn:aws:acm-pca:eu-central-2:123456789012:caa/ripe.eu-central-2|arn:aws:acm-pca:ap-northeast-1:123456789012:caa/apnic.ap-northeast-1|arn:aws:acm-pca:ap-south-2:123456789012:caa/apnic.ap-south-2',
            'default_perspective_count': '3',
            'enforce_distinct_rir_regions': '1',  # TODO may not need this...
            'hash_secret': 'test_secret'
        }
        with pytest.MonkeyPatch.context() as class_scoped_monkeypatch:
            for k, v in envvars.items():
                class_scoped_monkeypatch.setenv(k, v)
            yield class_scoped_monkeypatch  # restore the environment afterward

    def call_remote_perspective__should_make_aws_lambda_call_with_provided_arguments_and_return_check_response_as_json(self, set_env_variables, mocker):
        mocker.patch('botocore.client.BaseClient._make_api_call', side_effect=self.create_successful_boto3_api_call_response_for_dcv_check)
        dcv_check_request = ValidCheckCreator.create_valid_dns_check_request()
        mpic_coordinator_lambda_handler = MpicCoordinatorLambdaHandler()
        response_as_json = mpic_coordinator_lambda_handler.call_remote_perspective(RemotePerspective(code='us-west-1', rir='arin'),
                                                                                   CheckType.DCV,
                                                                                   dcv_check_request.model_dump_json())  # TODO fix to be object
        check_response = DcvCheckResponse.model_validate_json(response_as_json)
        assert check_response.check_passed is True
        # hijacking the value of 'perspective' to verify that the right arguments got passed to the call
        assert check_response.perspective == dcv_check_request.domain_or_ip_target

    def call_remote_perspective__should_return_error_response_as_json(self, set_env_variables, mocker):
        mocker.patch('botocore.client.BaseClient._make_api_call', side_effect=self.create_error_boto3_api_call_response)
        dcv_check_request = ValidCheckCreator.create_valid_dns_check_request()
        mpic_coordinator_lambda_handler = MpicCoordinatorLambdaHandler()
        response_as_json = mpic_coordinator_lambda_handler.call_remote_perspective(RemotePerspective(code='us-west-1', rir='arin'),
                                                                                   CheckType.DCV,
                                                                                   dcv_check_request.model_dump_json())
        assert response_as_json == 'Something went wrong'

    # noinspection PyMethodMayBeStatic
    def process_invocation__should_return_400_response_given_invalid_request_path(self, set_env_variables):
        event = {'path': 'invalid_path'}
        mpic_coordinator_lambda_handler = MpicCoordinatorLambdaHandler()
        response = mpic_coordinator_lambda_handler.process_invocation(event)
        assert response['statusCode'] == 400

    # noinspection PyMethodMayBeStatic
    def lambda_handler__should_coordinate_mpic_using_configured_mpic_coordinator(self, set_env_variables, mocker):
        mock_return_value = {
            'statusCode': 200,  # note: must be snakeCase
            'headers': {'Content-Type': 'application/json'},
            'body': TestMpicCoordinatorLambda.create_caa_mpic_response().model_dump_json()
        }

        mocker.patch('open_mpic_core.mpic_coordinator.mpic_coordinator.MpicCoordinator.coordinate_mpic',
                     return_value=mock_return_value)
        mpic_request = ValidMpicRequestCreator.create_valid_mpic_request(CheckType.CAA)
        event = {'path': RequestPath.MPIC, 'body': mpic_request.model_dump_json()}
        result = mpic_coordinator_lambda_function.lambda_handler(event, None)
        assert result == mock_return_value

    # noinspection PyUnusedLocal, PyMethodMayBeStatic
    def create_successful_boto3_api_call_response_for_dcv_check(self, lambda_method, lambda_configuration):
        check_request = DcvCheckRequest.model_validate_json(lambda_configuration['Payload'])
        # hijacking the value of 'perspective' to verify that the right arguments got passed to the call
        expected_response_body = DcvCheckResponse(perspective=check_request.domain_or_ip_target,
                                                  check_passed=True, details=DcvCheckResponseDetails())
        expected_response = {'statusCode': 200, 'body': expected_response_body.model_dump_json()}
        json_bytes = json.dumps(expected_response).encode('utf-8')
        file_like_response = io.BytesIO(json_bytes)
        streaming_body_response = StreamingBody(file_like_response, len(json_bytes))
        return {'Payload': streaming_body_response}

    # noinspection PyUnusedLocal, PyMethodMayBeStatic
    def create_error_boto3_api_call_response(self, lambda_method, lambda_configuration):
        # note: all perspective response details will be identical in these tests due to this mocking
        expected_response_body = 'Something went wrong'
        expected_response = {'statusCode': 500, 'body': expected_response_body}
        json_bytes = json.dumps(expected_response).encode('utf-8')
        file_like_response = io.BytesIO(json_bytes)
        streaming_body_response = StreamingBody(file_like_response, len(json_bytes))
        return {'Payload': streaming_body_response}

    @staticmethod
    def create_caa_mpic_response():
        caa_request = ValidMpicRequestCreator.create_valid_caa_mpic_request()
        return MpicCaaResponse(
            request_orchestration_parameters=caa_request.orchestration_parameters,
            actual_orchestration_parameters=MpicEffectiveOrchestrationParameters(
                perspective_count=3, quorum_count=2, attempt_count=1
            ),
            is_valid=True,
            perspectives=[],
            caa_check_parameters=caa_request.caa_check_parameters
        )


if __name__ == '__main__':
    pytest.main()
