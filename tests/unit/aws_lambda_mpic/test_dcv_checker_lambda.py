import time
import pytest

import aws_lambda_mpic.mpic_dcv_checker_lambda.mpic_dcv_checker_lambda_function as mpic_dcv_checker_lambda_function
from open_mpic_core.common_domain.validation_error import MpicValidationError
from open_mpic_core.common_domain.check_response_details import DcvHttpCheckResponseDetails
from open_mpic_core.common_domain.enum.dcv_validation_method import DcvValidationMethod
from open_mpic_core.common_domain.check_response import DcvCheckResponse
from open_mpic_core_test.test_util.valid_check_creator import ValidCheckCreator


# noinspection PyMethodMayBeStatic
class TestDcvCheckerLambda:
    @staticmethod
    @pytest.fixture(scope='class')
    def set_env_variables():
        envvars = {
            'AWS_REGION': 'us-east-1',
        }
        with pytest.MonkeyPatch.context() as class_scoped_monkeypatch:
            for k, v in envvars.items():
                class_scoped_monkeypatch.setenv(k, v)
            yield class_scoped_monkeypatch  # restore the environment afterward

    # noinspection PyMethodMayBeStatic
    def lambda_handler__should_do_dcv_check_using_configured_dcv_checker(self, set_env_variables, mocker):
        mock_dcv_response = TestDcvCheckerLambda.create_dcv_check_response()
        mock_return_value = {
            'statusCode': 200,  # note: must be snakeCase
            'headers': {'Content-Type': 'application/json'},
            'body': mock_dcv_response.model_dump_json()
        }
        mocker.patch('open_mpic_core.mpic_dcv_checker.mpic_dcv_checker.MpicDcvChecker.check_dcv', return_value=mock_dcv_response)
        dcv_check_request = ValidCheckCreator.create_valid_http_check_request()
        result = mpic_dcv_checker_lambda_function.lambda_handler(dcv_check_request, None)
        assert result == mock_return_value

    @pytest.mark.parametrize('error_type, error_message, expected_status_code', [
        ('404', 'Not Found', 404),
        ('No Answer', 'The DNS response does not contain an answer to the question', 500)
    ])
    def lambda_handler__should_return_appropriate_status_code_given_errors_in_response(
            self, error_type: str, error_message: str, expected_status_code: int, set_env_variables, mocker):
        mock_dcv_response = TestDcvCheckerLambda.create_dcv_check_response()
        mock_dcv_response.check_passed = False
        mock_dcv_response.errors = [(MpicValidationError(error_type=error_type, error_message=error_message))]
        mock_return_value = {
            'statusCode': expected_status_code,
            'headers': {'Content-Type': 'application/json'},
            'body': mock_dcv_response.model_dump_json()
        }
        mocker.patch('open_mpic_core.mpic_dcv_checker.mpic_dcv_checker.MpicDcvChecker.check_dcv', return_value=mock_dcv_response)
        dcv_check_request = ValidCheckCreator.create_valid_http_check_request()
        result = mpic_dcv_checker_lambda_function.lambda_handler(dcv_check_request, None)
        assert result == mock_return_value

    @staticmethod
    def create_dcv_check_response():
        return DcvCheckResponse(perspective_code='us-east-1', check_passed=True,
                                details=DcvHttpCheckResponseDetails(validation_method=DcvValidationMethod.WEBSITE_CHANGE_V2),
                                timestamp_ns=time.time_ns())


if __name__ == '__main__':
    pytest.main()
