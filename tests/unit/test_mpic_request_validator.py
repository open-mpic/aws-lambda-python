import sys

import pytest

from aws_lambda_python.common_domain.dcv_validation_method import DcvValidationMethod
from aws_lambda_python.mpic_coordinator.domain.request_path import RequestPath
from aws_lambda_python.mpic_coordinator.messages.validation_messages import ValidationMessages
from aws_lambda_python.mpic_coordinator.mpic_request_validator import MpicRequestValidator
from valid_request_creator import ValidRequestCreator


# TODO rename to TestMpicCommandValidator
# TODO rename all tests to is_command_valid__...
# noinspection PyMethodMayBeStatic
class TestMpicRequestValidator:
    @classmethod
    def setup_class(cls):
        cls.known_perspectives = ['p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'p7', 'p8', 'p9', 'p10']

    def is_request_valid__should_return_true_and_empty_list_given_valid_caa_check_request_with_perspective_count(self):
        command = ValidRequestCreator.create_valid_caa_check_command()
        is_request_valid, validation_issues = MpicRequestValidator.is_command_valid(RequestPath.CAA_CHECK, command, self.known_perspectives)
        assert is_request_valid is True
        assert len(validation_issues) == 0

    def is_request_valid__should_return_true_given_valid_caa_check_request_with_perspective_list_and_diagnostic_mode_true(self):
        command = ValidRequestCreator.create_valid_caa_check_command()
        command.system_params.perspectives = self.known_perspectives[:6]
        command.system_params.perspective_count = None
        is_request_valid, validation_issues = MpicRequestValidator.is_command_valid(RequestPath.CAA_CHECK, command, self.known_perspectives)
        assert is_request_valid is True
        assert len(validation_issues) == 0

    # def is_request_valid__should_return_false_and_message_given_caa_check_request_with_perspective_list_and_diagnostic_mode_false(self):

    @pytest.mark.parametrize('validation_method', [DcvValidationMethod.DNS_GENERIC, DcvValidationMethod.HTTP_GENERIC,
                                                   DcvValidationMethod.TLS_USING_ALPN])
    def is_request_valid__should_return_true_given_valid_dcv_check_request(self, validation_method):
        command = ValidRequestCreator.create_valid_dcv_check_command(validation_method)
        is_request_valid, validation_issues = MpicRequestValidator.is_command_valid(RequestPath.DCV_CHECK, command, self.known_perspectives)
        assert is_request_valid is True
        assert len(validation_issues) == 0

    def is_request_valid__should_return_true_given_valid_dcv_with_caa_check_request(self):
        command = ValidRequestCreator.create_valid_dcv_with_caa_check_command()
        is_request_valid, validation_issues = MpicRequestValidator.is_command_valid(RequestPath.DCV_WITH_CAA_CHECK, command, self.known_perspectives)
        assert is_request_valid is True
        assert len(validation_issues) == 0

    def is_request_valid__should_return_false_and_message_given_missing_api_version(self):
        command = ValidRequestCreator.create_valid_caa_check_command()
        command.api_version = None  # remove api-version field
        is_request_valid, validation_issues = MpicRequestValidator.is_command_valid(RequestPath.CAA_CHECK, command, self.known_perspectives)
        assert is_request_valid is False
        assert ValidationMessages.MISSING_API_VERSION.key in [issue.issue_type for issue in validation_issues]

    @pytest.mark.parametrize('api_version', ['0.0.1', '5.0.0', '1;0;0', '1.', '100', 'bad-api-version'])  # ~=1.0.0 is valid
    def is_request_valid__should_return_false_and_message_given_invalid_api_version(self, api_version):
        command = ValidRequestCreator.create_valid_caa_check_command()
        command.api_version = api_version
        is_request_valid, validation_issues = MpicRequestValidator.is_command_valid(RequestPath.CAA_CHECK, command, self.known_perspectives)
        assert is_request_valid is False
        assert ValidationMessages.INVALID_API_VERSION.key in [issue.issue_type for issue in validation_issues]
        invalid_api_version_issue = next(issue for issue in validation_issues if issue.issue_type == ValidationMessages.INVALID_API_VERSION.key)
        assert api_version in invalid_api_version_issue.message

    @pytest.mark.parametrize('request_path', ['/invalid-path'])  # do any other path types need testing?
    def is_request_valid__should_return_false_and_message_given_unsupported_request_path(self, request_path):
        command = ValidRequestCreator.create_valid_caa_check_command()
        is_request_valid, validation_issues = MpicRequestValidator.is_command_valid(request_path, command, self.known_perspectives)
        assert is_request_valid is False
        assert ValidationMessages.UNSUPPORTED_REQUEST_PATH.key in [issue.issue_type for issue in validation_issues]
        unsupported_request_path_issue = next(issue for issue in validation_issues if issue.issue_type == ValidationMessages.UNSUPPORTED_REQUEST_PATH.key)
        assert request_path in unsupported_request_path_issue.message

    def is_request_valid__should_return_false_and_message_given_missing_system_params(self):
        command = ValidRequestCreator.create_valid_caa_check_command()
        command.system_params = None  # remove system-params field
        is_request_valid, validation_issues = MpicRequestValidator.is_command_valid(RequestPath.CAA_CHECK, command, self.known_perspectives)
        assert is_request_valid is False
        assert ValidationMessages.MISSING_SYSTEM_PARAMS.key in [issue.issue_type for issue in validation_issues]

    def is_request_valid__should_return_false_and_message_given_missing_domain_or_ip_target(self):
        command = ValidRequestCreator.create_valid_caa_check_command()
        command.system_params.domain_or_ip_target = None  # remove domain-or-ip-target field
        is_request_valid, validation_issues = MpicRequestValidator.is_command_valid(RequestPath.CAA_CHECK, command, self.known_perspectives)
        assert is_request_valid is False
        assert ValidationMessages.MISSING_DOMAIN_OR_IP_TARGET.key in [issue.issue_type for issue in validation_issues]

    def is_request_valid__should_return_false_and_message_given_both_perspective_and_perspective_count_present(self):
        command = ValidRequestCreator.create_valid_caa_check_command()
        command.system_params.perspectives = self.known_perspectives[:6]
        command.system_params.perspective_count = 2
        is_request_valid, validation_issues = MpicRequestValidator.is_command_valid(RequestPath.CAA_CHECK, command, self.known_perspectives)
        assert is_request_valid is False
        assert ValidationMessages.PERSPECTIVES_WITH_PERSPECTIVE_COUNT.key in [issue.issue_type for issue in validation_issues]

    @pytest.mark.parametrize('perspective_count', [1, 0, -1, 'abc', sys.maxsize+1])
    def is_request_valid__should_return_false_and_message_given_invalid_perspective_count(self, perspective_count):
        command = ValidRequestCreator.create_valid_caa_check_command()
        command.system_params.perspective_count = perspective_count
        is_request_valid, validation_issues = MpicRequestValidator.is_command_valid(RequestPath.CAA_CHECK, command, self.known_perspectives)
        assert is_request_valid is False
        assert ValidationMessages.INVALID_PERSPECTIVE_COUNT.key in [issue.issue_type for issue in validation_issues]
        invalid_perspective_count_issue = next(issue for issue in validation_issues if issue.issue_type == ValidationMessages.INVALID_PERSPECTIVE_COUNT.key)
        assert str(perspective_count) in invalid_perspective_count_issue.message

    # TODO discuss enforcement of 500km distance between perspective regions. (And 2+ RIR requirement.)
    def is_request_valid__should_return_false_and_message_given_invalid_perspective_list(self):
        command = ValidRequestCreator.create_valid_caa_check_command()
        command.system_params.perspective_count = None
        command.system_params.perspectives = ['bad_p1', 'bad_p2', 'bad_p3', 'bad_p4', 'bad_p5', 'bad_p6']
        is_request_valid, validation_issues = MpicRequestValidator.is_command_valid(RequestPath.CAA_CHECK, command, self.known_perspectives)
        assert is_request_valid is False
        assert ValidationMessages.INVALID_PERSPECTIVE_LIST.key in [issue.issue_type for issue in validation_issues]

    # TODO should there be a more permissive validation (in diagnostic mode?) for quorum count?
    @pytest.mark.parametrize('quorum_count', [1, -1, 10, 'abc', sys.maxsize+1])
    def is_request_valid__should_return_false_and_message_given_invalid_quorum_count(self, quorum_count):
        command = ValidRequestCreator.create_valid_caa_check_command()
        command.system_params.quorum_count = quorum_count
        is_request_valid, validation_issues = MpicRequestValidator.is_command_valid(RequestPath.CAA_CHECK, command, self.known_perspectives)
        assert is_request_valid is False
        assert ValidationMessages.INVALID_QUORUM_COUNT.key in [issue.issue_type for issue in validation_issues]
        invalid_quorum_count_issue = next(issue for issue in validation_issues if issue.issue_type == ValidationMessages.INVALID_QUORUM_COUNT.key)
        assert str(quorum_count) in invalid_quorum_count_issue.message

    # TODO probably shouldn't allow a quorum count of zero, but that is an API spec update
    def is_request_valid__should_allow_quorum_count_of_zero(self):
        command = ValidRequestCreator.create_valid_caa_check_command()
        command.system_params.quorum_count = 0
        is_request_valid, validation_issues = MpicRequestValidator.is_command_valid(RequestPath.CAA_CHECK, command, self.known_perspectives)
        assert is_request_valid is True
        assert len(validation_issues) == 0

    def is_request_valid__should_return_false_and_message_given_invalid_certificate_type_specified(self):
        command = ValidRequestCreator.create_valid_caa_check_command()
        command.caa_details.certificate_type = 'invalid-certificate-type'
        is_request_valid, validation_issues = MpicRequestValidator.is_command_valid(RequestPath.CAA_CHECK, command, self.known_perspectives)
        assert is_request_valid is False
        assert ValidationMessages.INVALID_CERTIFICATE_TYPE.key in [issue.issue_type for issue in validation_issues]
        invalid_certificate_type_issue = next(issue for issue in validation_issues if issue.issue_type == ValidationMessages.INVALID_CERTIFICATE_TYPE.key)
        assert 'invalid-certificate-type' in invalid_certificate_type_issue.message

    def is_request_valid__should_return_false_and_message_given_missing_validation_method_for_dcv(self):
        command = ValidRequestCreator.create_valid_dcv_check_command()
        command.validation_method = None
        is_request_valid, validation_issues = MpicRequestValidator.is_command_valid(RequestPath.DCV_CHECK, command, self.known_perspectives)
        assert is_request_valid is False
        assert ValidationMessages.MISSING_VALIDATION_METHOD.key in [issue.issue_type for issue in validation_issues]

    def is_request_valid__should_return_false_and_message_given_invalid_validation_method_specified(self):
        command = ValidRequestCreator.create_valid_dcv_check_command()
        command.validation_method = 'invalid-validation-method'
        is_request_valid, validation_issues = MpicRequestValidator.is_command_valid(RequestPath.DCV_CHECK, command, self.known_perspectives)
        assert is_request_valid is False
        assert ValidationMessages.INVALID_VALIDATION_METHOD.key in [issue.issue_type for issue in validation_issues]
        invalid_validation_method_issue = next(issue for issue in validation_issues if issue.issue_type == ValidationMessages.INVALID_VALIDATION_METHOD.key)
        assert 'invalid-validation-method' in invalid_validation_method_issue.message

    def is_request_valid__should_return_false_and_message_given_missing_validation_details_for_dcv(self):
        command = ValidRequestCreator.create_valid_dcv_check_command()
        command.validation_details = None
        is_request_valid, validation_issues = MpicRequestValidator.is_command_valid(RequestPath.DCV_CHECK, command, self.known_perspectives)
        assert is_request_valid is False
        assert ValidationMessages.MISSING_VALIDATION_DETAILS.key in [issue.issue_type for issue in validation_issues]

    @pytest.mark.parametrize('validation_method', [DcvValidationMethod.DNS_GENERIC, DcvValidationMethod.HTTP_GENERIC,
                                                   DcvValidationMethod.TLS_USING_ALPN])
    def is_request_valid__should_return_false_and_message_given_missing_expected_challenge_for_dcv(self, validation_method):
        command = ValidRequestCreator.create_valid_dcv_check_command(validation_method)
        command.validation_details.expected_challenge = None
        is_request_valid, validation_issues = MpicRequestValidator.is_command_valid(RequestPath.DCV_CHECK, command, self.known_perspectives)
        assert is_request_valid is False
        assert ValidationMessages.MISSING_EXPECTED_CHALLENGE.key in [issue.issue_type for issue in validation_issues]

    def is_request_valid__should_return_false_and_message_given_missing_prefix_for_dns_validation(self):
        command = ValidRequestCreator.create_valid_dcv_check_command(DcvValidationMethod.DNS_GENERIC)
        command.validation_details.prefix = None
        is_request_valid, validation_issues = MpicRequestValidator.is_command_valid(RequestPath.DCV_CHECK, command, self.known_perspectives)
        assert is_request_valid is False
        assert ValidationMessages.MISSING_PREFIX.key in [issue.issue_type for issue in validation_issues]

    def is_request_valid__should_return_false_and_message_given_missing_record_type_for_dns_validation(self):
        command = ValidRequestCreator.create_valid_dcv_check_command(DcvValidationMethod.DNS_GENERIC)
        command.validation_details.record_type = None
        is_request_valid, validation_issues = MpicRequestValidator.is_command_valid(RequestPath.DCV_CHECK, command, self.known_perspectives)
        assert is_request_valid is False
        assert ValidationMessages.MISSING_RECORD_TYPE.key in [issue.issue_type for issue in validation_issues]

    def is_request_valid__should_return_false_and_message_given_missing_path_for_http_validation(self):
        command = ValidRequestCreator.create_valid_dcv_check_command(DcvValidationMethod.HTTP_GENERIC)
        command.validation_details.path = None
        is_request_valid, validation_issues = MpicRequestValidator.is_command_valid(RequestPath.DCV_CHECK, command, self.known_perspectives)
        assert is_request_valid is False
        assert ValidationMessages.MISSING_PATH.key in [issue.issue_type for issue in validation_issues]

    def is_request_valid__should_return_multiple_messages_given_multiple_validation_issues(self):
        command = ValidRequestCreator.create_valid_dcv_check_command()
        command.system_params.domain_or_ip_target = None
        command.validation_method = None
        is_request_valid, validation_issues = MpicRequestValidator.is_command_valid(RequestPath.DCV_CHECK, command, self.known_perspectives)
        assert is_request_valid is False
        assert len(validation_issues) == 2
        assert ValidationMessages.MISSING_VALIDATION_METHOD.key in [issue.issue_type for issue in validation_issues]
        assert ValidationMessages.MISSING_DOMAIN_OR_IP_TARGET.key in [issue.issue_type for issue in validation_issues]


if __name__ == '__main__':
    pytest.main()
