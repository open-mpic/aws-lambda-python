import time

import pytest

import aws_lambda_mpic.mpic_caa_checker_lambda.mpic_caa_checker_lambda_function as mpic_caa_checker_lambda_function
from open_mpic_core.common_domain.check_response import CaaCheckResponse, CaaCheckResponseDetails
from unit.test_util.valid_check_creator import ValidCheckCreator


class TestCaaCheckerLambda:
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
    def lambda_handler__should_do_caa_check_using_configured_caa_checker(self, set_env_variables, mocker):
        mock_return_value = {
            'statusCode': 200,  # note: must be snakeCase
            'headers': {'Content-Type': 'application/json'},
            'body': TestCaaCheckerLambda.create_caa_check_response().model_dump_json()
        }
        mocker.patch('open_mpic_core.mpic_caa_checker.mpic_caa_checker.MpicCaaChecker.check_caa', return_value=mock_return_value)
        caa_check_request = ValidCheckCreator.create_valid_caa_check_request()
        event = caa_check_request.model_dump_json()  # TODO go back to using an object rather than a serialized string
        result = mpic_caa_checker_lambda_function.lambda_handler(event, None)
        assert result == mock_return_value

    @staticmethod
    def create_caa_check_response():
        return CaaCheckResponse(perspective='arin.us-east-1', check_passed=True,
                                details=CaaCheckResponseDetails(caa_record_present=True,
                                                                found_at='example.com',
                                                                response='dummy_response'),
                                timestamp_ns=time.time_ns())


if __name__ == '__main__':
    pytest.main()
