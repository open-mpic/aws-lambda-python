import sys

import pytest

from aws_lambda_python.mpic_coordinator.domain.dcv_validation_method import DcvValidationMethod
from aws_lambda_python.mpic_coordinator.domain.dns_record_type import DnsRecordType
from aws_lambda_python.mpic_coordinator.messages.validation_messages import ValidationMessages
from aws_lambda_python.mpic_coordinator.mpic_request_validator import MpicRequestValidator


# noinspection PyMethodMayBeStatic
class TestMpicRequestValidator:
    def __create_valid_caa_check_request(self):
        return {
            'api-version': '1.0.0',
            'system-params': {'identifier': 'test', 'perspective-count': 6, 'quorum': 4},
            'caa-details': {'certificate-type': 'tls-server'}
        }

    def __create_valid_dcv_check_request(self, validation_method=DcvValidationMethod.DNS_GENERIC):
        validation_details = {}
        match validation_method:
            case DcvValidationMethod.DNS_GENERIC:
                validation_details = {'prefix': 'test', 'record-type': DnsRecordType.A, 'expected-challenge': 'test'}
            case DcvValidationMethod.HTTP_GENERIC:
                validation_details = {'path': 'http://example.com', 'expected-challenge': 'test'}  # noqa (not https)
            case DcvValidationMethod.TLS_USING_ALPN:
                validation_details = {'expected-challenge': 'test'}
        return {
            'api-version': '1.0.0',
            'system-params': {'identifier': 'test', 'perspective-count': 6, 'quorum': 4},
            'validation-method': validation_method,
            'validation-details': validation_details
        }

    def is_request_body_valid__should_return_true_and_empty_message_list_given_valid_caa_check_request(self):
        body = self.__create_valid_caa_check_request()
        is_body_valid, body_validation_issues = MpicRequestValidator.is_request_body_valid('/caa-check', body)
        assert is_body_valid is True
        assert len(body_validation_issues) == 0

    @pytest.mark.parametrize('validation_method', [DcvValidationMethod.DNS_GENERIC, DcvValidationMethod.HTTP_GENERIC,
                                                   DcvValidationMethod.TLS_USING_ALPN])
    def is_request_body_valid__should_return_true_and_empty_message_list_given_valid_dcv_check_request(self, validation_method):
        body = self.__create_valid_dcv_check_request(validation_method)
        is_body_valid, body_validation_issues = MpicRequestValidator.is_request_body_valid('/validation', body)
        assert is_body_valid is True
        assert len(body_validation_issues) == 0

    def is_request_body_valid__should_return_false_and_message_given_missing_api_version(self):
        body = self.__create_valid_caa_check_request()
        del body['api-version']  # remove api-version field
        is_body_valid, body_validation_issues = MpicRequestValidator.is_request_body_valid('/caa-check', body)
        assert is_body_valid is False
        assert ValidationMessages.MISSING_API_VERSION.key in [issue.issue_type for issue in body_validation_issues]

    @pytest.mark.parametrize('api_version', ['0.0.1', '5.0.0', '1;0;0', '1.', '100', 'bad-api-version'])  # ~=1.0.0 is valid
    def is_request_body_valid__should_return_false_and_message_given_invalid_api_version(self, api_version):
        body = self.__create_valid_caa_check_request()
        body['api-version'] = api_version
        is_body_valid, body_validation_issues = MpicRequestValidator.is_request_body_valid('/caa-check', body)
        assert is_body_valid is False
        assert ValidationMessages.INVALID_API_VERSION.key in [issue.issue_type for issue in body_validation_issues]
        # get the message for the first issue with the key 'invalid-api-version'
        invalid_api_version_issue = next(issue for issue in body_validation_issues if issue.issue_type == ValidationMessages.INVALID_API_VERSION.key)
        assert api_version in invalid_api_version_issue.message

    @pytest.mark.parametrize('request_path', ['/invalid-path'])  # do any other path types need testing?
    def is_request_body_valid__should_return_false_and_message_given_unsupported_request_path(self, request_path):
        body = self.__create_valid_caa_check_request()
        is_body_valid, body_validation_issues = MpicRequestValidator.is_request_body_valid(request_path, body)
        assert is_body_valid is False
        assert 'unsupported-request-path' in body_validation_issues

    def is_request_body_valid__should_return_false_and_message_given_missing_system_params(self):
        body = self.__create_valid_caa_check_request()
        del body['system-params']  # remove system-params field
        is_body_valid, body_validation_issues = MpicRequestValidator.is_request_body_valid('/caa-check', body)
        assert is_body_valid is False
        assert 'missing-system-params' in body_validation_issues

    # TODO rename when you rename identifier field in the spec (recommend "domain_or_ip_target" for highest clarity)
    def is_request_body_valid__should_return_false_and_message_given_missing_identifier(self):
        body = self.__create_valid_caa_check_request()
        del body['system-params']['identifier']  # remove identifier field
        is_body_valid, body_validation_issues = MpicRequestValidator.is_request_body_valid('/caa-check', body)
        assert is_body_valid is False
        assert 'missing-domain-or-ip-target' in body_validation_issues

    def is_request_body_valid__should_return_false_and_message_given_both_perspective_and_perspective_count_present(self):
        body = self.__create_valid_caa_check_request()
        body['system-params']['perspectives'] = ['perspective1', 'perspective2']
        body['system-params']['perspective-count'] = 2
        is_body_valid, body_validation_issues = MpicRequestValidator.is_request_body_valid('/caa-check', body)
        assert is_body_valid is False
        assert 'contains-both-perspectives-and-perspective-count' in body_validation_issues

    @pytest.mark.xfail  # TODO enable test when validation logic for perspective count is implemented
    @pytest.mark.parametrize('perspective_count', [1, 0, -1, 'abc', sys.maxsize+1])
    def is_request_body_valid__should_return_false_and_message_given_invalid_perspective_count(self, perspective_count):
        body = self.__create_valid_caa_check_request()
        body['system-params']['perspective-count'] = perspective_count
        is_body_valid, body_validation_issues = MpicRequestValidator.is_request_body_valid('/caa-check', body)
        assert is_body_valid is False
        assert 'invalid-perspective-count' in body_validation_issues

    @pytest.mark.xfail  # TODO enable test when validation logic for quorum count is implemented
    @pytest.mark.parametrize('quorum_count', [1, 0, -1, 10, 'abc', sys.maxsize+1])
    def is_request_body_valid__should_return_false_and_message_given_invalid_quorum_count(self, quorum_count):
        body = self.__create_valid_caa_check_request()
        body['system-params']['quorum'] = quorum_count
        is_body_valid, body_validation_issues = MpicRequestValidator.is_request_body_valid('/caa-check', body)
        assert is_body_valid is False
        assert 'invalid-quorum-count' in body_validation_issues

    def is_request_body_valid__should_return_false_and_message_given_missing_certificate_type_for_caa_check(self):
        body = self.__create_valid_caa_check_request()
        del body['caa-details']['certificate-type']
        is_body_valid, body_validation_issues = MpicRequestValidator.is_request_body_valid('/caa-check', body)
        assert is_body_valid is False
        assert 'missing-certificate-type-in-caa-details' in body_validation_issues

    def is_request_body_valid__should_return_false_and_message_given_invalid_certificate_type_specified(self):
        body = self.__create_valid_caa_check_request()
        body['caa-details']['certificate-type'] = 'invalid-certificate-type'
        is_body_valid, body_validation_issues = MpicRequestValidator.is_request_body_valid('/caa-check', body)
        assert is_body_valid is False
        assert 'invalid-certificate-type-in-caa-details' in body_validation_issues

    def is_request_body_valid__should_return_false_and_message_given_missing_validation_method_for_dcv(self):
        body = self.__create_valid_dcv_check_request()
        del body['validation-method']
        is_body_valid, body_validation_issues = MpicRequestValidator.is_request_body_valid('/validation', body)
        assert is_body_valid is False
        assert 'missing-validation-method' in body_validation_issues

    def is_request_body_valid__should_return_false_and_message_given_invalid_validation_method_specified(self):
        body = self.__create_valid_dcv_check_request()
        # noinspection PyTypedDict
        body['validation-method'] = 'invalid-validation-method'
        is_body_valid, body_validation_issues = MpicRequestValidator.is_request_body_valid('/validation', body)
        assert is_body_valid is False
        assert 'invalid-validation-method' in body_validation_issues

    def is_request_body_valid__should_return_false_and_message_given_missing_validation_details_for_dcv(self):
        body = self.__create_valid_dcv_check_request()
        del body['validation-details']
        is_body_valid, body_validation_issues = MpicRequestValidator.is_request_body_valid('/validation', body)
        assert is_body_valid is False
        assert 'missing-validation-details' in body_validation_issues

    @pytest.mark.parametrize('validation_method', [DcvValidationMethod.DNS_GENERIC, DcvValidationMethod.HTTP_GENERIC,
                                                   DcvValidationMethod.TLS_USING_ALPN])
    def is_request_body_valid__should_return_false_and_message_given_missing_expected_challenge_for_dcv(self, validation_method):
        body = self.__create_valid_dcv_check_request(validation_method)
        del body['validation-details']['expected-challenge']
        is_body_valid, body_validation_issues = MpicRequestValidator.is_request_body_valid('/validation', body)
        assert is_body_valid is False
        assert 'missing-expected-challenge-in-validation-details' in body_validation_issues

    def is_request_body_valid__should_return_false_and_message_given_missing_prefix_for_dns_validation(self):
        body = self.__create_valid_dcv_check_request(DcvValidationMethod.DNS_GENERIC)
        del body['validation-details']['prefix']
        is_body_valid, body_validation_issues = MpicRequestValidator.is_request_body_valid('/validation', body)
        assert is_body_valid is False
        assert 'missing-prefix-in-validation-details' in body_validation_issues

    def is_request_body_valid__should_return_false_and_message_given_missing_record_type_for_dns_validation(self):
        body = self.__create_valid_dcv_check_request(DcvValidationMethod.DNS_GENERIC)
        del body['validation-details']['record-type']
        is_body_valid, body_validation_issues = MpicRequestValidator.is_request_body_valid('/validation', body)
        assert is_body_valid is False
        assert 'missing-record-type-in-validation-details' in body_validation_issues

    def is_request_body_valid__should_return_false_and_message_given_missing_path_for_http_validation(self):
        body = self.__create_valid_dcv_check_request(DcvValidationMethod.HTTP_GENERIC)
        del body['validation-details']['path']
        is_body_valid, body_validation_issues = MpicRequestValidator.is_request_body_valid('/validation', body)
        assert is_body_valid is False
        assert 'missing-path-in-validation-details' in body_validation_issues


if __name__ == '__main__':
    pytest.main()
