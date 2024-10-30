import json

import dns
import pytest
from aws_lambda_python.common_domain.check_request import DcvCheckRequest
from aws_lambda_python.common_domain.check_response import DcvCheckResponse, DcvCheckResponseDetails
from aws_lambda_python.common_domain.enum.dcv_validation_method import DcvValidationMethod
from aws_lambda_python.common_domain.enum.dns_record_type import DnsRecordType
from aws_lambda_python.common_domain.remote_perspective import RemotePerspective
from aws_lambda_python.mpic_dcv_checker.mpic_dcv_checker import MpicDcvChecker

from mock_dns_object_creator import MockDnsObjectCreator
from valid_check_creator import ValidCheckCreator


# noinspection PyMethodMayBeStatic
class TestMpicDcvChecker:
    @staticmethod
    @pytest.fixture(scope='class')
    def set_env_variables():
        envvars = {
            'default_caa_domains': 'ca1.com|ca2.net|ca3.org',
            'AWS_REGION': 'us-east-4',
            'rir_region': 'arin',
        }
        with pytest.MonkeyPatch.context() as class_scoped_monkeypatch:
            for k, v in envvars.items():
                class_scoped_monkeypatch.setenv(k, v)
            yield class_scoped_monkeypatch  # restore the environment afterward

    @staticmethod
    def create_configured_dcv_checker():
        return MpicDcvChecker(RemotePerspective.from_rir_code("arin.us-east-4"))

    # integration test of a sort -- only mocking dns methods rather than remaining class methods
    @pytest.mark.parametrize('validation_method, record_type', [(DcvValidationMethod.HTTP_GENERIC, None),
                                                                (DcvValidationMethod.DNS_GENERIC, DnsRecordType.TXT),
                                                                (DcvValidationMethod.DNS_GENERIC, DnsRecordType.CNAME)])
    def check_dcv__should_perform_appropriate_check_and_return_200_and_allow_issuance_given_target_record_found(self, set_env_variables, validation_method, record_type, mocker):
        dcv_request = None
        match validation_method:
            case DcvValidationMethod.HTTP_GENERIC:
                dcv_request = ValidCheckCreator.create_valid_http_check_request()
                self.mock_http_related_calls(dcv_request, mocker)
            case DcvValidationMethod.DNS_GENERIC:
                dcv_request = ValidCheckCreator.create_valid_dns_check_request(record_type)
                self.mock_dns_related_calls(dcv_request, mocker)
        dcv_checker = TestMpicDcvChecker.create_configured_dcv_checker()
        result = dcv_checker.check_dcv(dcv_request)
        assert result['statusCode'] == 200
        result_body = json.loads(result['body'])
        response_object = DcvCheckResponse.model_validate(result_body)
        response_object.timestamp_ns = None  # ignore timestamp for comparison
        expected_response = DcvCheckResponse(perspective='arin.us-east-4', check_passed=True, details=DcvCheckResponseDetails())
        assert json.dumps(response_object.model_dump()) == json.dumps(expected_response.model_dump())

    def perform_http_validation__should_return_check_passed_true_with_details_given_request_token_file_found(self, set_env_variables, mocker):
        dcv_request = ValidCheckCreator.create_valid_http_check_request()
        self.mock_http_related_calls(dcv_request, mocker)
        dcv_checker = TestMpicDcvChecker.create_configured_dcv_checker()
        response = dcv_checker.perform_http_validation(dcv_request)
        assert response['statusCode'] == 200
        dcv_check_response = DcvCheckResponse.model_validate(json.loads(response['body']))
        assert dcv_check_response.check_passed is True
        assert dcv_check_response.perspective == 'arin.us-east-4'
        assert dcv_check_response.timestamp_ns is not None

    def perform_http_validation__should_return_check_passed_false_with_details_given_request_token_file_not_found(self, set_env_variables, mocker):
        dcv_request = ValidCheckCreator.create_valid_http_check_request()
        mocker.patch('requests.get', return_value=type('Response', (object,), {'status_code': 404, 'reason': 'Not Found'})())
        dcv_checker = TestMpicDcvChecker.create_configured_dcv_checker()
        response = dcv_checker.perform_http_validation(dcv_request)
        assert response['statusCode'] == 404
        dcv_check_response = DcvCheckResponse.model_validate(json.loads(response['body']))
        assert dcv_check_response.check_passed is False
        assert dcv_check_response.errors[0].error_type == '404'
        assert dcv_check_response.errors[0].error_message == 'Not Found'
        assert dcv_check_response.timestamp_ns is not None

    @pytest.mark.parametrize('record_type', [DnsRecordType.TXT, DnsRecordType.CNAME])
    def perform_dns_validation__should_return_check_passed_true_with_details_given_expected_dns_record_found(self, set_env_variables, record_type, mocker):
        dcv_request = ValidCheckCreator.create_valid_dns_check_request(record_type)
        self.mock_dns_related_calls(dcv_request, mocker)
        dcv_checker = TestMpicDcvChecker.create_configured_dcv_checker()
        response = dcv_checker.perform_dns_validation(dcv_request)
        assert response['statusCode'] == 200
        dcv_check_response = DcvCheckResponse.model_validate(json.loads(response['body']))
        assert dcv_check_response.check_passed is True
        assert dcv_check_response.perspective == 'arin.us-east-4'
        assert dcv_check_response.timestamp_ns is not None

    def perform_dns_validation__should_return_check_passed_false_with_details_given_expected_dns_record_not_found(self, set_env_variables, mocker):
        dcv_request = ValidCheckCreator.create_valid_dns_check_request()
        mocker.patch('dns.resolver.resolve', side_effect=lambda domain_name, rdtype: self.raise_(dns.resolver.NoAnswer))
        dcv_checker = TestMpicDcvChecker.create_configured_dcv_checker()
        response = dcv_checker.perform_dns_validation(dcv_request)
        assert response['statusCode'] == 500
        dcv_check_response = DcvCheckResponse.model_validate(json.loads(response['body']))
        assert dcv_check_response.check_passed is False
        assert dcv_check_response.errors[0].error_type == dns.resolver.NoAnswer.__name__
        assert 'answer' in dcv_check_response.errors[0].error_message
        assert dcv_check_response.timestamp_ns is not None

    def raise_(self, ex):
        # noinspection PyUnusedLocal
        def _raise(*args, **kwargs):
            raise ex
        return _raise()

    def mock_http_related_calls(self, dcv_request: DcvCheckRequest, mocker):
        expected_url = f"http://{dcv_request.domain_or_ip_target}/{dcv_request.dcv_check_parameters.validation_details.http_token_path}"  # noqa E501 (http)
        expected_challenge = dcv_request.dcv_check_parameters.validation_details.challenge_value
        mocker.patch('requests.get', side_effect=lambda url: (
            type('Response', (object,), {'status_code': 200, 'text': expected_challenge})() if url == expected_url else
            type('Response', (object,), {'status_code': 404, 'reason': 'Not Found'})()
        ))

    def mock_dns_related_calls(self, dcv_request: DcvCheckRequest, mocker):
        dcv_details = dcv_request.dcv_check_parameters.validation_details
        expected_domain = f"{dcv_details.dns_name_prefix}.{dcv_request.domain_or_ip_target}"
        record_data = {'value': dcv_details.challenge_value}
        test_dns_query_answer = MockDnsObjectCreator.create_dns_query_answer(dcv_request.domain_or_ip_target,
                                                                             dcv_details.dns_name_prefix,
                                                                             dcv_details.dns_record_type,
                                                                             record_data, mocker)
        mocker.patch('dns.resolver.resolve', side_effect=lambda domain_name, rdtype: (
            test_dns_query_answer if domain_name == expected_domain else self.raise_(dns.resolver.NoAnswer)
        ))


if __name__ == '__main__':
    pytest.main()
