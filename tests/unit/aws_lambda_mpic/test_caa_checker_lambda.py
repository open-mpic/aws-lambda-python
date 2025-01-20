import time

import dns
import pytest

import aws_lambda_mpic.mpic_caa_checker_lambda.mpic_caa_checker_lambda_function as mpic_caa_checker_lambda_function
from open_mpic_core.common_domain.check_response import CaaCheckResponse, CaaCheckResponseDetails
from open_mpic_core_test.test_util.mock_dns_object_creator import MockDnsObjectCreator
from open_mpic_core_test.test_util.valid_check_creator import ValidCheckCreator


# noinspection PyMethodMayBeStatic
class TestCaaCheckerLambda:
    @staticmethod
    @pytest.fixture(scope='class')
    def set_env_variables():
        envvars = {
            'AWS_REGION': 'us-east-1',
            'default_caa_domains': 'ca1.com|ca2.org|ca3.net',
            'log_level': 'TRACE'
        }
        with pytest.MonkeyPatch.context() as class_scoped_monkeypatch:
            for k, v in envvars.items():
                class_scoped_monkeypatch.setenv(k, v)
            yield class_scoped_monkeypatch  # restore the environment afterward

    # noinspection PyMethodMayBeStatic
    def lambda_handler__should_do_caa_check_using_configured_caa_checker(self, set_env_variables, mocker):
        mock_caa_result = TestCaaCheckerLambda.create_caa_check_response()
        mock_return_value = {
            'statusCode': 200,  # note: must be snakeCase
            'headers': {'Content-Type': 'application/json'},
            'body': mock_caa_result.model_dump_json()
        }
        mocker.patch('open_mpic_core.mpic_caa_checker.mpic_caa_checker.MpicCaaChecker.check_caa', return_value=mock_caa_result)
        caa_check_request = ValidCheckCreator.create_valid_caa_check_request()
        result = mpic_caa_checker_lambda_function.lambda_handler(caa_check_request, None)
        assert result == mock_return_value

    def lambda_handler__should_set_log_level_of_caa_checker(self, set_env_variables, setup_logging, mocker):
        caa_check_request = ValidCheckCreator.create_valid_caa_check_request()

        records = [MockDnsObjectCreator.create_caa_record(0, 'issue', 'ca1.org')]
        mock_rrset = MockDnsObjectCreator.create_rrset(dns.rdatatype.CAA, *records)
        mock_domain = dns.name.from_text(caa_check_request.domain_or_ip_target)
        mock_return = (mock_rrset, mock_domain)
        mocker.patch('open_mpic_core.mpic_caa_checker.mpic_caa_checker.MpicCaaChecker.find_caa_records_and_domain',
                     return_value=mock_return)

        result = mpic_caa_checker_lambda_function.lambda_handler(caa_check_request, None)
        assert result['statusCode'] == 200
        log_contents = setup_logging.getvalue()
        assert all(text in log_contents for text in ['MpicCaaChecker', 'TRACE'])  # Verify the log level was set

    @staticmethod
    def create_caa_check_response():
        return CaaCheckResponse(perspective_code='us-east-1', check_passed=True,
                                details=CaaCheckResponseDetails(caa_record_present=True,
                                                                found_at='example.com'),
                                timestamp_ns=time.time_ns())


if __name__ == '__main__':
    pytest.main()
