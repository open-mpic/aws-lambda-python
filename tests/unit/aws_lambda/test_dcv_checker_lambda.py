import time

import pytest

import aws_lambda_python.mpic_dcv_checker_lambda.mpic_dcv_checker_lambda_function as mpic_dcv_checker_lambda_function
from open_mpic_core.common_domain.check_response import DcvCheckResponse, DcvCheckResponseDetails
from unit.valid_check_creator import ValidCheckCreator


class TestDcvCheckerLambda:
    @staticmethod
    @pytest.fixture(scope='class')
    def set_env_variables():
        envvars = {
            'rir_region': 'arin',
            'AWS_REGION': 'us-east-1',
            'default_caa_domains': 'ca1.com|ca2.org|ca3.net'
        }
        with pytest.MonkeyPatch.context() as class_scoped_monkeypatch:
            for k, v in envvars.items():
                class_scoped_monkeypatch.setenv(k, v)
            yield class_scoped_monkeypatch  # restore the environment afterward

    # noinspection PyMethodMayBeStatic
    def lambda_handler__should_do_dcv_check_using_configured_dcv_checker(self, set_env_variables, mocker):
        mock_return_value = {
            'statusCode': 200,  # note: must be snakeCase
            'headers': {'Content-Type': 'application/json'},
            'body': TestDcvCheckerLambda.create_dcv_check_response().model_dump_json()
        }
        mocker.patch('open_mpic_core.mpic_dcv_checker.mpic_dcv_checker.MpicDcvChecker.check_dcv', return_value=mock_return_value)
        dcv_check_request = ValidCheckCreator.create_valid_http_check_request()
        event = dcv_check_request.model_dump_json()  # TODO go back to using an object rather than a serialized string
        result = mpic_dcv_checker_lambda_function.lambda_handler(event, None)
        assert result == mock_return_value

    @staticmethod
    def create_dcv_check_response():
        return DcvCheckResponse(perspective='arin.us-east-1', check_passed=True,
                                details=DcvCheckResponseDetails(),
                                timestamp_ns=time.time_ns())


if __name__ == '__main__':
    pytest.main()
