import time
import pytest

from open_mpic_core import MpicValidationError
from open_mpic_core import DcvHttpCheckResponseDetails
from open_mpic_core import DcvValidationMethod
from open_mpic_core import DcvCheckResponse

import aws_lambda_mpic.mpic_dcv_checker_lambda.mpic_dcv_checker_lambda_function as mpic_dcv_checker_lambda_function

from open_mpic_core_test.test_util.valid_check_creator import ValidCheckCreator

from aws_lambda_mpic.mpic_dcv_checker_lambda.mpic_dcv_checker_lambda_function import MpicDcvCheckerLambdaHandler
from unit.aws_lambda_mpic.conftest import setup_logging


# noinspection PyMethodMayBeStatic
class TestDcvCheckerLambda:
    @staticmethod
    @pytest.fixture(scope="class")
    def set_env_variables():
        envvars = {
            "AWS_REGION": "us-east-1",
            "log_level": "TRACE",
            "http_client_timeout_seconds": "11",
            "dns_timeout_seconds": "12",
            "dns_resolution_lifetime_seconds": "13",
        }
        with pytest.MonkeyPatch.context() as class_scoped_monkeypatch:
            for k, v in envvars.items():
                class_scoped_monkeypatch.setenv(k, v)
            yield class_scoped_monkeypatch  # restore the environment afterward

    # noinspection PyMethodMayBeStatic
    def lambda_handler__should_do_dcv_check_using_configured_dcv_checker(self, set_env_variables, mocker):
        mock_dcv_response = TestDcvCheckerLambda.create_dcv_check_response()
        mock_return_value = {
            "statusCode": 200,  # note: must be snakeCase
            "headers": {"Content-Type": "application/json"},
            "body": mock_dcv_response.model_dump_json(),
        }
        mocker.patch("open_mpic_core.MpicDcvChecker.check_dcv", return_value=mock_dcv_response)
        dcv_check_request = ValidCheckCreator.create_valid_http_check_request()
        result = mpic_dcv_checker_lambda_function.lambda_handler(dcv_check_request, None)
        assert result == mock_return_value

    # fmt: off
    @pytest.mark.parametrize('error_type, error_message, expected_status_code', [
        ('404', 'Not Found', 404),
        ('No Answer', 'The DNS response does not contain an answer to the question', 500)
    ])
    # fmt: on
    def lambda_handler__should_return_appropriate_status_code_given_errors_in_response(
        self, error_type: str, error_message: str, expected_status_code: int, set_env_variables, mocker
    ):
        mock_dcv_response = TestDcvCheckerLambda.create_dcv_check_response()
        mock_dcv_response.check_passed = False
        mock_dcv_response.errors = [(MpicValidationError(error_type=error_type, error_message=error_message))]
        mock_return_value = {
            "statusCode": expected_status_code,
            "headers": {"Content-Type": "application/json"},
            "body": mock_dcv_response.model_dump_json(),
        }
        mocker.patch("open_mpic_core.MpicDcvChecker.check_dcv", return_value=mock_dcv_response)
        dcv_check_request = ValidCheckCreator.create_valid_http_check_request()
        result = mpic_dcv_checker_lambda_function.lambda_handler(dcv_check_request, None)
        assert result == mock_return_value

    def lambda_handler__should_set_log_level_of_dcv_checker(self, set_env_variables, mocker, setup_logging):
        dcv_check_request = ValidCheckCreator.create_valid_http_check_request()
        mocker.patch(
            "open_mpic_core.MpicDcvChecker.perform_http_based_validation",
            return_value=TestDcvCheckerLambda.create_dcv_check_response(),
        )
        result = mpic_dcv_checker_lambda_function.lambda_handler(dcv_check_request, None)
        assert result["statusCode"] == 200
        log_contents = setup_logging.getvalue()
        assert all(text in log_contents for text in ["MpicDcvChecker", "TRACE"])  # Verify the log level was set

    async def lambda_handler__should_set_dns_timeout_configuration_of_dcv_checker(self, set_env_variables):
        # a bit leaky in terms of implementation but there's not an easy way to enforce this otherwise
        configured_dcv_checker = MpicDcvCheckerLambdaHandler().dcv_checker
        assert configured_dcv_checker.resolver.timeout == 12.0
        assert configured_dcv_checker.resolver.lifetime == 13.0
        async with configured_dcv_checker.get_async_http_client() as http_client:
            assert http_client.timeout.total == 11.0

    @staticmethod
    def create_dcv_check_response():
        return DcvCheckResponse(
            check_passed=True,
            details=DcvHttpCheckResponseDetails(validation_method=DcvValidationMethod.WEBSITE_CHANGE),
            timestamp_ns=time.time_ns(),
        )


if __name__ == "__main__":
    pytest.main()
