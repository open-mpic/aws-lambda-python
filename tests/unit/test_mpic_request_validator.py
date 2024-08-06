import pytest

from aws_lambda_python.mpic_coordinator.domain.dcv_validation_method import DcvValidationMethod
from aws_lambda_python.mpic_coordinator.domain.dns_record_type import DnsRecordType
from aws_lambda_python.mpic_coordinator.mpic_request_validator import MpicRequestValidator


# noinspection PyMethodMayBeStatic
class TestMpicRequestValidator:
    def __create_valid_caa_check_request(self):
        return {
            'api-version': '1.0.0',
            'system-params': {'identifier': 'test'},
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
            'system-params': {'identifier': 'test'},
            'validation-method': validation_method,
            'validation-details': validation_details
        }

    def validate_request_body__should_return_true_and_empty_message_list_given_valid_caa_check_request(self):
        body = self.__create_valid_caa_check_request()
        is_body_valid, body_validation_issues = MpicRequestValidator.validate_request_body('/caa-check', body)
        assert is_body_valid is True
        assert len(body_validation_issues) == 0

    def validate_request_body__should_return_true_and_empty_message_list_given_valid_dcv_check_request(self):
        body = self.__create_valid_dcv_check_request()
        is_body_valid, body_validation_issues = MpicRequestValidator.validate_request_body('/validation', body)
        assert is_body_valid is True
        assert len(body_validation_issues) == 0

    def validate_request_body__should_return_false_and_message_given_missing_api_version(self):
        body = self.__create_valid_caa_check_request()
        del body['api-version']  # remove api-version field
        is_body_valid, body_validation_issues = MpicRequestValidator.validate_request_body('/caa-check', body)
        assert is_body_valid is False
        assert 'missing-api-version' in body_validation_issues

    def validate_request_body__should_return_false_and_message_given_missing_system_params(self):
        body = self.__create_valid_caa_check_request()
        del body['system-params']  # remove system-params field
        is_body_valid, body_validation_issues = MpicRequestValidator.validate_request_body('/caa-check', body)
        assert is_body_valid is False
        assert 'missing-system-params' in body_validation_issues

    # TODO rename when you rename identifier field in the spec
    def validate_request_body__should_return_false_and_message_given_missing_identifier(self):
        body = self.__create_valid_caa_check_request()
        del body['system-params']['identifier']  # remove identifier field
        is_body_valid, body_validation_issues = MpicRequestValidator.validate_request_body('/caa-check', body)
        assert is_body_valid is False
        assert 'missing-domain-or-ip-target' in body_validation_issues

    def validate_request_body__should_return_false_and_message_given_both_perspective_and_perspective_count_present(self):
        body = self.__create_valid_caa_check_request()
        body['system-params']['perspectives'] = ['perspective1', 'perspective2']
        body['system-params']['perspective-count'] = 2
        is_body_valid, body_validation_issues = MpicRequestValidator.validate_request_body('/caa-check', body)
        assert is_body_valid is False
        assert 'contains-both-perspectives-and-perspective-count' in body_validation_issues

    def validate_request_body__should_return_false_and_message_given_missing_certificate_type_for_caa_check(self):
        body = self.__create_valid_caa_check_request()
        del body['caa-details']['certificate-type']
        is_body_valid, body_validation_issues = MpicRequestValidator.validate_request_body('/caa-check', body)
        assert is_body_valid is False
        assert 'missing-certificate-type-in-caa-details' in body_validation_issues

    def validate_request_body__should_return_false_and_message_given_invalid_certificate_type_specified(self):
        body = self.__create_valid_caa_check_request()
        body['caa-details']['certificate-type'] = 'invalid-certificate-type'
        is_body_valid, body_validation_issues = MpicRequestValidator.validate_request_body('/caa-check', body)
        assert is_body_valid is False
        assert 'invalid-certificate-type-in-caa-details' in body_validation_issues

    def validate_request_body__should_return_false_and_message_given_missing_validation_method_for_dcv(self):
        body = self.__create_valid_dcv_check_request()
        del body['validation-method']
        is_body_valid, body_validation_issues = MpicRequestValidator.validate_request_body('/validation', body)
        assert is_body_valid is False
        assert 'missing-validation-method' in body_validation_issues

    def validate_request_body__should_return_false_and_message_given_invalid_validation_method_specified(self):
        body = self.__create_valid_dcv_check_request()
        # noinspection PyTypedDict
        body['validation-method'] = 'invalid-validation-method'
        is_body_valid, body_validation_issues = MpicRequestValidator.validate_request_body('/validation', body)
        assert is_body_valid is False
        assert 'invalid-validation-method' in body_validation_issues

    def validate_request_body__should_return_false_and_message_given_missing_validation_details_for_dcv(self):
        body = self.__create_valid_dcv_check_request()
        del body['validation-details']
        is_body_valid, body_validation_issues = MpicRequestValidator.validate_request_body('/validation', body)
        assert is_body_valid is False
        assert 'missing-validation-details' in body_validation_issues

    @pytest.mark.parametrize('validation_method', [DcvValidationMethod.DNS_GENERIC, DcvValidationMethod.HTTP_GENERIC,
                                                   DcvValidationMethod.TLS_USING_ALPN])
    def validate_request_body__should_return_false_and_message_given_missing_expected_challenge_for_dcv(self, validation_method):
        body = self.__create_valid_dcv_check_request(validation_method)
        del body['validation-details']['expected-challenge']
        is_body_valid, body_validation_issues = MpicRequestValidator.validate_request_body('/validation', body)
        assert is_body_valid is False
        assert 'missing-expected-challenge-in-validation-details' in body_validation_issues

    def validate_request_body__should_return_false_and_message_given_missing_prefix_for_dns_validation(self):
        body = self.__create_valid_dcv_check_request(DcvValidationMethod.DNS_GENERIC)
        del body['validation-details']['prefix']
        is_body_valid, body_validation_issues = MpicRequestValidator.validate_request_body('/validation', body)
        assert is_body_valid is False
        assert 'missing-prefix-in-validation-details' in body_validation_issues

    def validate_request_body__should_return_false_and_message_given_missing_record_type_for_dns_validation(self):
        body = self.__create_valid_dcv_check_request(DcvValidationMethod.DNS_GENERIC)
        del body['validation-details']['record-type']
        is_body_valid, body_validation_issues = MpicRequestValidator.validate_request_body('/validation', body)
        assert is_body_valid is False
        assert 'missing-record-type-in-validation-details' in body_validation_issues

    def validate_request_body__should_return_false_and_message_given_missing_path_for_http_validation(self):
        body = self.__create_valid_dcv_check_request(DcvValidationMethod.HTTP_GENERIC)
        del body['validation-details']['path']
        is_body_valid, body_validation_issues = MpicRequestValidator.validate_request_body('/validation', body)
        assert is_body_valid is False
        assert 'missing-path-in-validation-details' in body_validation_issues


if __name__ == '__main__':
    pytest.main()
