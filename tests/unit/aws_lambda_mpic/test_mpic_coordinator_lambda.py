import io
import json
from datetime import datetime
from importlib import resources
from unittest.mock import AsyncMock

import pytest
import yaml
from aws_lambda_powertools.utilities.parser.models import (
    APIGatewayProxyEventModel,
    APIGatewayEventRequestContext,
    APIGatewayEventIdentity,
)
from pydantic import TypeAdapter, BaseModel

from open_mpic_core import RemotePerspective
from open_mpic_core import DcvCheckRequest, DcvCheckResponse, CaaCheckResponse, PerspectiveResponse
from open_mpic_core import CheckType
from open_mpic_core import DcvDnsCheckResponseDetails, CaaCheckResponseDetails
from open_mpic_core import DcvValidationMethod
from open_mpic_core import MpicEffectiveOrchestrationParameters
from open_mpic_core import MpicCaaResponse
from botocore.response import StreamingBody
import aws_lambda_mpic.mpic_coordinator_lambda.mpic_coordinator_lambda_function as mpic_coordinator_lambda_function
from aws_lambda_mpic.mpic_coordinator_lambda.mpic_coordinator_lambda_function import (
    MpicCoordinatorLambdaHandler,
    LambdaExecutionException,
    PerspectiveEndpoints,
    PerspectiveEndpointInfo,
)

from open_mpic_core_test.test_util.valid_mpic_request_creator import ValidMpicRequestCreator
from open_mpic_core_test.test_util.valid_check_creator import ValidCheckCreator


# noinspection PyMethodMayBeStatic
class TestMpicCoordinatorLambda:
    @staticmethod
    @pytest.fixture(scope="class")
    def set_env_variables():
        perspectives_as_dict = {
            "us-east-1": PerspectiveEndpoints(
                caa_endpoint_info=PerspectiveEndpointInfo(arn="arn:aws:us-east-1:123:caa/us-east-1"),
                dcv_endpoint_info=PerspectiveEndpointInfo(arn="arn:aws:us-east-1:123:dcv/us-east-1"),
            ),
            "us-west-1": PerspectiveEndpoints(
                caa_endpoint_info=PerspectiveEndpointInfo(arn="arn:aws:us-west-1:123:caa/us-west-1"),
                dcv_endpoint_info=PerspectiveEndpointInfo(arn="arn:aws:us-west-1:123:dcv/us-west-1"),
            ),
            "eu-west-2": PerspectiveEndpoints(
                caa_endpoint_info=PerspectiveEndpointInfo(arn="arn:aws:eu-west-2:123:caa/eu-west-2"),
                dcv_endpoint_info=PerspectiveEndpointInfo(arn="arn:aws:eu-west-2:123:dcv/eu-west-2"),
            ),
            "eu-central-2": PerspectiveEndpoints(
                caa_endpoint_info=PerspectiveEndpointInfo(arn="arn:aws:eu-central-2:123:caa/eu-central-2"),
                dcv_endpoint_info=PerspectiveEndpointInfo(arn="arn:aws:eu-central-2:123:dcv/eu-central-2"),
            ),
            "ap-northeast-1": PerspectiveEndpoints(
                caa_endpoint_info=PerspectiveEndpointInfo(arn="arn:aws:ap-northeast-1:123:caa/ap-northeast-1"),
                dcv_endpoint_info=PerspectiveEndpointInfo(arn="arn:aws:ap-northeast-1:123:dcv/ap-northeast-1"),
            ),
            "ap-south-2": PerspectiveEndpoints(
                caa_endpoint_info=PerspectiveEndpointInfo(arn="arn:aws:ap-south-2:123:caa/ap-south-2"),
                dcv_endpoint_info=PerspectiveEndpointInfo(arn="arn:aws:ap-south-2:123:dcv/ap-south-2"),
            ),
        }
        # fmt: on
        envvars = {
            "perspectives": json.dumps({k: v.model_dump() for k, v in perspectives_as_dict.items()}),
            "default_perspective_count": "3",
            "hash_secret": "test_secret",
            "log_level": "TRACE",
        }
        with pytest.MonkeyPatch.context() as class_scoped_monkeypatch:
            for k, v in envvars.items():
                class_scoped_monkeypatch.setenv(k, v)
            yield class_scoped_monkeypatch  # restore the environment afterward

    async def call_remote_perspective__should_make_aws_lambda_call_with_provided_arguments_and_return_check_response(
        self, set_env_variables, mocker
    ):
        lambda_handler, mock_client = await self.mock_lambda_handler_for_lambda_invoke(mocker, self.create_successful_aioboto3_response_for_dcv_check)

        dcv_check_request = ValidCheckCreator.create_valid_dns_check_request()
        perspective_code = "us-west-1"
        check_response = await lambda_handler.call_remote_perspective(
            RemotePerspective(code=perspective_code, rir="arin"), CheckType.DCV, dcv_check_request
        )
        assert check_response.check_passed is True
        # hijacking the value of 'details.found_at' to verify that the right arguments got passed to the call
        assert check_response.details.found_at == dcv_check_request.domain_or_ip_target

        function_endpoint_info = lambda_handler.remotes_per_perspective_per_check_type[CheckType.DCV][perspective_code]

        # Verify the mock was called correctly
        mock_client.invoke.assert_called_once_with(
            FunctionName=function_endpoint_info.arn,
            InvocationType="RequestResponse",
            Payload=dcv_check_request.model_dump_json(),
        )

    async def call_remote_perspective__should_make_aws_lambda_call_and_handle_lambda_execution_exceptions(
        self, set_env_variables, mocker
    ):
        lambda_handler, mock_client = await self.mock_lambda_handler_for_lambda_invoke(mocker, self.create_error_aioboto3_response)

        class Dummy(BaseModel):
            pass

        with pytest.raises(LambdaExecutionException) as exc_info:
            await lambda_handler.call_remote_perspective(
                RemotePerspective(code="us-west-1", rir="dummy"), CheckType.DCV, Dummy()
            )        
        assert exc_info.value.args[0] == "Lambda execution error: {\"errorMessage\": \"some message\"}"

    def lambda_handler__should_return_400_error_and_details_given_invalid_request_body(self):
        request = ValidMpicRequestCreator.create_valid_dcv_mpic_request()
        # noinspection PyTypeChecker
        request.domain_or_ip_target = None
        api_request = TestMpicCoordinatorLambda.create_api_gateway_request()
        api_request.body = request.model_dump_json()
        # noinspection PyTypeChecker
        result = mpic_coordinator_lambda_function.lambda_handler(api_request, None)
        assert result["statusCode"] == 400
        result_body = json.loads(result["body"])
        assert result_body["validation_issues"][0]["type"] == "string_type"

    def lambda_handler__should_return_400_error_and_details_given_invalid_check_type(self):
        request = ValidMpicRequestCreator.create_valid_dcv_mpic_request()
        request.check_type = "invalid_check_type"
        api_request = TestMpicCoordinatorLambda.create_api_gateway_request()
        api_request.body = request.model_dump_json()
        # noinspection PyTypeChecker
        result = mpic_coordinator_lambda_function.lambda_handler(api_request, None)
        assert result["statusCode"] == 400
        result_body = json.loads(result["body"])
        assert result_body["validation_issues"][0]["type"] == "literal_error"

    def lambda_handler__should_return_400_error_given_logically_invalid_request(self, set_env_variables):
        request = ValidMpicRequestCreator.create_valid_dcv_mpic_request()
        request.orchestration_parameters.perspective_count = 1
        api_request = TestMpicCoordinatorLambda.create_api_gateway_request()
        api_request.body = request.model_dump_json()
        # noinspection PyTypeChecker
        result = mpic_coordinator_lambda_function.lambda_handler(api_request, None)
        assert result["statusCode"] == 400
        result_body = json.loads(result["body"])
        assert result_body["validation_issues"][0]["issue_type"] == "invalid-perspective-count"

    def lambda_handler__should_return_500_error_given_other_unexpected_errors(self, set_env_variables, mocker):
        request = ValidMpicRequestCreator.create_valid_dcv_mpic_request()
        api_request = TestMpicCoordinatorLambda.create_api_gateway_request()
        api_request.body = request.model_dump_json()
        mocker.patch(
            "open_mpic_core.mpic_coordinator.mpic_coordinator.MpicCoordinator.coordinate_mpic",
            side_effect=Exception("Something went wrong"),
        )
        # noinspection PyTypeChecker
        result = mpic_coordinator_lambda_function.lambda_handler(api_request, None)
        assert result["statusCode"] == 500

    def lambda_handler__should_coordinate_mpic_using_configured_mpic_coordinator(self, set_env_variables, mocker):
        mpic_request = ValidMpicRequestCreator.create_valid_mpic_request(CheckType.CAA)
        api_request = TestMpicCoordinatorLambda.create_api_gateway_request()
        api_request.body = mpic_request.model_dump_json()
        mock_return_value = TestMpicCoordinatorLambda.create_caa_mpic_response()
        mocker.patch(
            "open_mpic_core.mpic_coordinator.mpic_coordinator.MpicCoordinator.coordinate_mpic",
            return_value=mock_return_value,
        )
        expected_response = {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": mock_return_value.model_dump_json(),
        }
        # noinspection PyTypeChecker
        result = mpic_coordinator_lambda_function.lambda_handler(api_request, None)
        assert result == expected_response

    def lambda_handler__should_set_log_level_for_coordinator(self, set_env_variables, setup_logging, mocker):
        mpic_request = ValidMpicRequestCreator.create_valid_mpic_request(CheckType.CAA)
        api_request = TestMpicCoordinatorLambda.create_api_gateway_request()
        api_request.body = mpic_request.model_dump_json()
        mocked_perspective_responses = [
            PerspectiveResponse(
                perspective_code=code,
                check_response=CaaCheckResponse(
                    check_passed=True, details=CaaCheckResponseDetails(caa_record_present=False)
                ),
            )
            for code in ["us-east-1", "us-west-1", "eu-west-2", "eu-central-2", "ap-northeast-1", "ap-south-2"]
        ]
        mock_return = mocked_perspective_responses

        mocker.patch("open_mpic_core.MpicCoordinator.call_checkers_and_collect_responses", return_value=mock_return)
        # noinspection PyTypeChecker
        result = mpic_coordinator_lambda_function.lambda_handler(api_request, None)
        assert result["statusCode"] == 200
        log_contents = setup_logging.getvalue()
        assert all(text in log_contents for text in ["MpicCoordinator", "TRACE"])  # Verify the log level was set

    def load_aws_region_config__should_return_dict_of_aws_regions_with_proximity_info_by_region_code(self):
        mpic_coordinator_lambda_handler = MpicCoordinatorLambdaHandler()
        loaded_aws_regions = mpic_coordinator_lambda_handler.load_aws_region_config()
        all_possible_perspectives = TestMpicCoordinatorLambda.get_perspectives_by_code_dict_from_file()
        assert len(loaded_aws_regions.keys()) == len(all_possible_perspectives.keys())
        # for example, us-east-1 is too close to us-east-2
        assert "us-east-2" in loaded_aws_regions["us-east-1"].too_close_codes
        assert "us-east-1" in loaded_aws_regions["us-east-2"].too_close_codes

    def constructor__should_initialize_mpic_coordinator_and_set_target_perspectives(self, set_env_variables):
        mpic_coordinator_lambda_handler = MpicCoordinatorLambdaHandler()
        all_possible_perspectives = TestMpicCoordinatorLambda.get_perspectives_by_code_dict_from_file()
        for target_perspective in mpic_coordinator_lambda_handler.target_perspectives:
            assert target_perspective in all_possible_perspectives.values()
        mpic_coordinator = mpic_coordinator_lambda_handler.mpic_coordinator
        assert len(mpic_coordinator.target_perspectives) == 6
        assert mpic_coordinator.default_perspective_count == 3
        assert mpic_coordinator.hash_secret == "test_secret"

    # noinspection PyUnusedLocal
    def create_successful_boto3_api_call_response_for_dcv_check(self, lambda_method, lambda_configuration):
        check_request = DcvCheckRequest.model_validate_json(lambda_configuration["Payload"])
        # hijacking the value of 'perspective_code' to verify that the right arguments got passed to the call
        expected_response_body = DcvCheckResponse(
            check_passed=True,
            details=DcvDnsCheckResponseDetails(validation_method=DcvValidationMethod.ACME_DNS_01),
        )
        expected_response = {"statusCode": 200, "body": expected_response_body.model_dump_json()}
        json_bytes = json.dumps(expected_response).encode("utf-8")
        file_like_response = io.BytesIO(json_bytes)
        streaming_body_response = StreamingBody(file_like_response, len(json_bytes))
        return {"Payload": streaming_body_response}

    # noinspection PyUnusedLocal
    async def create_successful_aioboto3_response_for_dcv_check(self, *args, **kwargs):
        check_request = DcvCheckRequest.model_validate_json(kwargs["Payload"])
        # hijacking the value of 'found_at' to verify that the right arguments got passed to the call
        expected_response_body = DcvCheckResponse(
            check_passed=True,
            details=DcvDnsCheckResponseDetails(
                validation_method=DcvValidationMethod.ACME_DNS_01, found_at=check_request.domain_or_ip_target
            ),
        )
        expected_response = {"statusCode": 200, "body": expected_response_body.model_dump_json()}
        json_bytes = json.dumps(expected_response).encode("utf-8")

        # Mock the response structure that aioboto3 would return
        class MockStreamingBody:
            # noinspection PyMethodMayBeStatic
            async def read(self):
                return json_bytes

        return {"Payload": MockStreamingBody()}
    
    # noinspection PyUnusedLocal
    async def create_error_aioboto3_response(self, *args, **kwargs):
        expected_response = {"errorMessage": "some message"}
        json_bytes = json.dumps(expected_response).encode("utf-8")

        class MockStreamingBody:
            # noinspection PyMethodMayBeStatic
            async def read(self):
                return json_bytes
            
        # See https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/lambda/client/invoke.html, "Response Structure"
        return {"Payload": MockStreamingBody(), "FunctionError": None}

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
            caa_check_parameters=caa_request.caa_check_parameters,
        )

    # noinspection PyUnusedLocal
    @staticmethod
    def create_caa_perspective_response(*args, **kwargs) -> CaaCheckResponse:
        return CaaCheckResponse(
            check_passed=True,
            details=CaaCheckResponseDetails(caa_record_present=False),
        )

    @staticmethod
    def create_api_gateway_request():
        request = APIGatewayProxyEventModel(
            resource="whatever",
            path="/mpic",
            httpMethod="POST",
            headers={"Content-Type": "application/json"},
            multiValueHeaders={},
            requestContext=APIGatewayEventRequestContext(
                accountId="whatever",
                apiId="whatever",
                stage="whatever",
                protocol="whatever",
                identity=APIGatewayEventIdentity(sourceIp="test-invoke-source-ip"),
                requestId="whatever",
                requestTime="whatever",
                requestTimeEpoch=datetime.now(),
                resourcePath="whatever",
                httpMethod="POST",
                path="/mpic",
            ),
        )
        return request

    @staticmethod
    def get_perspectives_by_code_dict_from_file() -> dict[str, RemotePerspective]:
        with resources.files("resources").joinpath("aws_region_config.yaml").open("r") as file:
            perspectives_yaml = yaml.safe_load(file)
            perspective_type_adapter = TypeAdapter(list[RemotePerspective])
            perspectives = perspective_type_adapter.validate_python(perspectives_yaml["aws_available_regions"])
            return {perspective.code: perspective for perspective in perspectives}

    async def mock_lambda_handler_for_lambda_invoke(self, mocker, lambda_invoke_side_effect):
        # Mock the aioboto3 client creation and context manager
        mock_client = AsyncMock()
        mock_client.invoke = AsyncMock(side_effect=lambda_invoke_side_effect)
        # Mock the __aenter__ method that gets called in initialize_client_pools()
        mock_client.__aenter__.return_value = mock_client
        # Mock the session creation and client initialization
        mock_session = mocker.patch("aioboto3.Session")
        mock_session.return_value.client.return_value = mock_client
        lambda_handler = MpicCoordinatorLambdaHandler()
        await lambda_handler.initialize_client_pools()
        return lambda_handler, mock_client

if __name__ == "__main__":
    pytest.main()
