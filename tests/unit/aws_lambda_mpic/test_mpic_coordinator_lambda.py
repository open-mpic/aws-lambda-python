import io
import json
import os
from datetime import datetime
from importlib import resources

import pytest
import yaml
from aws_lambda_powertools.utilities.parser.models import APIGatewayProxyEventModel, APIGatewayEventRequestContext, \
    APIGatewayEventIdentity
from pydantic import ValidationError, TypeAdapter

from open_mpic_core.common_domain.check_request import DcvCheckRequest
from open_mpic_core.common_domain.check_response import DcvCheckResponse
from open_mpic_core.common_domain.enum.check_type import CheckType
from open_mpic_core.common_domain.remote_perspective import RemotePerspective
from open_mpic_core.common_domain.check_response_details import DcvDnsCheckResponseDetails
from open_mpic_core.common_domain.enum.dcv_validation_method import DcvValidationMethod
from open_mpic_core.mpic_coordinator.domain.mpic_orchestration_parameters import MpicEffectiveOrchestrationParameters
from open_mpic_core.mpic_coordinator.domain.mpic_response import MpicCaaResponse
from aws_lambda_mpic.mpic_coordinator_lambda.mpic_coordinator_lambda_function import MpicCoordinatorLambdaHandler
from botocore.response import StreamingBody
import aws_lambda_mpic.mpic_coordinator_lambda.mpic_coordinator_lambda_function as mpic_coordinator_lambda_function

from unit.test_util.valid_check_creator import ValidCheckCreator
from unit.test_util.valid_mpic_request_creator import ValidMpicRequestCreator


# noinspection PyMethodMayBeStatic
class TestMpicCoordinatorLambda:
    @staticmethod
    @pytest.fixture(scope='class')
    def set_env_variables():
        envvars = {
            'perspective_names': 'arin.us-east-1|arin.us-west-1|ripe.eu-west-2|ripe.eu-central-2|apnic.ap-northeast-1|apnic.ap-south-2',
            'dcv_arns': 'arn:aws:acm-pca:us-east-1:123456789012:validator/arin.us-east-1|arn:aws:acm-pca:us-west-1:123456789012:validator/arin.us-west-1|arn:aws:acm-pca:eu-west-2:123456789012:validator/ripe.eu-west-2|arn:aws:acm-pca:eu-central-2:123456789012:validator/ripe.eu-central-2|arn:aws:acm-pca:ap-northeast-1:123456789012:validator/apnic.ap-northeast-1|arn:aws:acm-pca:ap-south-2:123456789012:validator/apnic.ap-south-2',
            'caa_arns': 'arn:aws:acm-pca:us-east-1:123456789012:caa/arin.us-east-1|arn:aws:acm-pca:us-west-1:123456789012:caa/arin.us-west-1|arn:aws:acm-pca:eu-west-2:123456789012:caa/ripe.eu-west-2|arn:aws:acm-pca:eu-central-2:123456789012:caa/ripe.eu-central-2|arn:aws:acm-pca:ap-northeast-1:123456789012:caa/apnic.ap-northeast-1|arn:aws:acm-pca:ap-south-2:123456789012:caa/apnic.ap-south-2',
            'default_perspective_count': '3',
            'hash_secret': 'test_secret'
        }
        with pytest.MonkeyPatch.context() as class_scoped_monkeypatch:
            for k, v in envvars.items():
                class_scoped_monkeypatch.setenv(k, v)
            yield class_scoped_monkeypatch  # restore the environment afterward

    def call_remote_perspective__should_make_aws_lambda_call_with_provided_arguments_and_return_check_response(self, set_env_variables, mocker):
        mocker.patch('botocore.client.BaseClient._make_api_call', side_effect=self.create_successful_boto3_api_call_response_for_dcv_check)
        dcv_check_request = ValidCheckCreator.create_valid_dns_check_request()
        mpic_coordinator_lambda_handler = MpicCoordinatorLambdaHandler()
        check_response = mpic_coordinator_lambda_handler.call_remote_perspective(RemotePerspective(code='us-west-1', rir='arin'),
                                                                                 CheckType.DCV,
                                                                                 dcv_check_request)
        assert check_response.check_passed is True
        # hijacking the value of 'perspective' to verify that the right arguments got passed to the call
        assert check_response.perspective_code == dcv_check_request.domain_or_ip_target

    def lambda_handler__should_return_400_error_and_details_given_invalid_request_body(self):
        request = ValidMpicRequestCreator.create_valid_dcv_mpic_request()
        request.domain_or_ip_target = None
        api_request = TestMpicCoordinatorLambda.create_api_gateway_request()
        api_request.body = request.model_dump_json()
        result = mpic_coordinator_lambda_function.lambda_handler(api_request, None)
        assert result['statusCode'] == 400
        result_body = json.loads(result['body'])
        assert result_body['validation_issues'][0]['type'] == 'string_type'

    def lambda_handler__should_return_400_error_and_details_given_invalid_check_type(self):
        request = ValidMpicRequestCreator.create_valid_dcv_mpic_request()
        request.check_type = 'invalid_check_type'
        api_request = TestMpicCoordinatorLambda.create_api_gateway_request()
        api_request.body = request.model_dump_json()
        result = mpic_coordinator_lambda_function.lambda_handler(api_request, None)
        assert result['statusCode'] == 400
        result_body = json.loads(result['body'])
        assert result_body['validation_issues'][0]['type'] == 'union_tag_invalid'

    def lambda_handler__should_return_400_error_given_logically_invalid_request(self):
        request = ValidMpicRequestCreator.create_valid_dcv_mpic_request()
        request.orchestration_parameters.perspective_count = 1
        api_request = TestMpicCoordinatorLambda.create_api_gateway_request()
        api_request.body = request.model_dump_json()
        result = mpic_coordinator_lambda_function.lambda_handler(api_request, None)
        assert result['statusCode'] == 400

    def lambda_handler__should_return_500_error_given_other_unexpected_errors(self, set_env_variables, mocker):
        request = ValidMpicRequestCreator.create_valid_dcv_mpic_request()
        api_request = TestMpicCoordinatorLambda.create_api_gateway_request()
        api_request.body = request.model_dump_json()
        mocker.patch('open_mpic_core.mpic_coordinator.mpic_coordinator.MpicCoordinator.coordinate_mpic',
                     side_effect=Exception('Something went wrong'))
        result = mpic_coordinator_lambda_function.lambda_handler(api_request, None)
        assert result['statusCode'] == 500

    def lambda_handler__should_coordinate_mpic_using_configured_mpic_coordinator(self, set_env_variables, mocker):
        mpic_request = ValidMpicRequestCreator.create_valid_mpic_request(CheckType.CAA)
        api_request = TestMpicCoordinatorLambda.create_api_gateway_request()
        api_request.body = mpic_request.model_dump_json()
        mock_return_value = TestMpicCoordinatorLambda.create_caa_mpic_response()
        mocker.patch('open_mpic_core.mpic_coordinator.mpic_coordinator.MpicCoordinator.coordinate_mpic',
                     return_value=mock_return_value)
        expected_response = {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': mock_return_value.model_dump_json()
        }
        result = mpic_coordinator_lambda_function.lambda_handler(api_request, None)
        assert result == expected_response

    def load_aws_region_config__should_return_dict_of_aws_regions_with_proximity_info_by_region_code(self):
        mpic_coordinator_lambda_handler = MpicCoordinatorLambdaHandler()
        loaded_aws_regions = mpic_coordinator_lambda_handler.load_aws_region_config()
        all_possible_perspectives = TestMpicCoordinatorLambda.get_perspectives_by_code_dict_from_file()
        assert len(loaded_aws_regions.keys()) == len(all_possible_perspectives.keys())
        # for example, us-east-1 is too close to us-east-2
        assert 'us-east-2' in loaded_aws_regions['us-east-1'].too_close_codes
        assert 'us-east-1' in loaded_aws_regions['us-east-2'].too_close_codes

    def constructor__should_initialize_mpic_coordinator_and_set_target_perspectives(self, set_env_variables):
        mpic_coordinator_lambda_handler = MpicCoordinatorLambdaHandler()
        all_possible_perspectives = TestMpicCoordinatorLambda.get_perspectives_by_code_dict_from_file()
        named_perspectives = os.environ['perspective_names'].split('|')
        mpic_coordinator = mpic_coordinator_lambda_handler.mpic_coordinator
        us_east_1_perspective = all_possible_perspectives['us-east-1']
        assert us_east_1_perspective in mpic_coordinator.target_perspectives
        assert len(named_perspectives) == len(mpic_coordinator.target_perspectives)
        assert mpic_coordinator.hash_secret == 'test_secret'

    # noinspection PyUnusedLocal
    def create_successful_boto3_api_call_response_for_dcv_check(self, lambda_method, lambda_configuration):
        check_request = DcvCheckRequest.model_validate_json(lambda_configuration['Payload'])
        # hijacking the value of 'perspective' to verify that the right arguments got passed to the call
        expected_response_body = DcvCheckResponse(perspective_code=check_request.domain_or_ip_target,
                                                  check_passed=True, details=DcvDnsCheckResponseDetails(validation_method=DcvValidationMethod.ACME_DNS_01))
        expected_response = {'statusCode': 200, 'body': expected_response_body.model_dump_json()}
        json_bytes = json.dumps(expected_response).encode('utf-8')
        file_like_response = io.BytesIO(json_bytes)
        streaming_body_response = StreamingBody(file_like_response, len(json_bytes))
        return {'Payload': streaming_body_response}

    # noinspection PyUnusedLocal
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

    @staticmethod
    def create_api_gateway_request():
        request = APIGatewayProxyEventModel(
            resource='whatever', path='/mpic',
            httpMethod='POST', headers={'Content-Type': 'application/json'}, multiValueHeaders={},
            requestContext=APIGatewayEventRequestContext(
                accountId='whatever', apiId='whatever', stage='whatever', protocol='whatever',
                identity=APIGatewayEventIdentity(
                    sourceIp='test-invoke-source-ip'
                ),
                requestId='whatever', requestTime='whatever', requestTimeEpoch=datetime.now(),
                resourcePath='whatever', httpMethod='POST', path='/mpic'
            ),
        )
        return request

    @staticmethod
    def get_perspectives_by_code_dict_from_file() -> dict[str, RemotePerspective]:
        perspectives_yaml = yaml.safe_load(resources.open_text('resources', 'aws_region_config.yaml'))
        perspective_type_adapter = TypeAdapter(list[RemotePerspective])
        perspectives = perspective_type_adapter.validate_python(perspectives_yaml['aws_available_regions'])
        return {perspective.code: perspective for perspective in perspectives}


if __name__ == '__main__':
    pytest.main()
