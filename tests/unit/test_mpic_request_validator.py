import sys
import pytest

from aws_lambda_python.common_domain.enum.dcv_validation_method import DcvValidationMethod
from aws_lambda_python.mpic_coordinator.domain.enum.request_path import RequestPath
from aws_lambda_python.mpic_coordinator.messages.validation_messages import ValidationMessages
from aws_lambda_python.mpic_coordinator.mpic_request_validator import MpicRequestValidator
from valid_request_creator import ValidRequestCreator


# noinspection PyMethodMayBeStatic
class TestMpicRequestValidator:
    @classmethod
    def setup_class(cls):
        cls.known_perspectives = ['p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'p7', 'p8', 'p9', 'p10']

    def is_request_valid__should_return_true_and_empty_list_given_valid_caa_check_request_with_perspective_count(self):
        request = ValidRequestCreator.create_valid_caa_check_request()
        is_request_valid, validation_issues = MpicRequestValidator.is_request_valid(RequestPath.CAA_CHECK, request, self.known_perspectives)
        assert is_request_valid is True
        assert len(validation_issues) == 0

    def is_request_valid__should_return_true_given_valid_caa_check_request_with_perspective_list_and_diagnostic_mode_true(self):
        request = ValidRequestCreator.create_valid_caa_check_request()
        request.orchestration_parameters.perspectives = self.known_perspectives[:6]
        request.orchestration_parameters.perspective_count = None
        is_request_valid, validation_issues = MpicRequestValidator.is_request_valid(RequestPath.CAA_CHECK, request, self.known_perspectives, True)
        assert is_request_valid is True
        assert len(validation_issues) == 0

    def is_request_valid__should_return_false_and_message_given_caa_check_request_with_perspective_list_and_diagnostic_mode_false(self):
        request = ValidRequestCreator.create_valid_caa_check_request()
        request.orchestration_parameters.perspectives = self.known_perspectives[:6]
        request.orchestration_parameters.perspective_count = None
        is_request_valid, validation_issues = MpicRequestValidator.is_request_valid(RequestPath.CAA_CHECK, request, self.known_perspectives, False)
        assert is_request_valid is False
        assert ValidationMessages.PERSPECTIVES_NOT_IN_DIAGNOSTIC_MODE.key in [issue.issue_type for issue in validation_issues]

    @pytest.mark.parametrize('validation_method', [DcvValidationMethod.DNS_GENERIC, DcvValidationMethod.HTTP_GENERIC,
                                                   DcvValidationMethod.TLS_USING_ALPN])
    def is_request_valid__should_return_true_given_valid_dcv_check_request(self, validation_method):
        request = ValidRequestCreator.create_valid_dcv_check_request(validation_method)
        is_request_valid, validation_issues = MpicRequestValidator.is_request_valid(RequestPath.DCV_CHECK, request, self.known_perspectives)
        assert is_request_valid is True
        assert len(validation_issues) == 0

    def is_request_valid__should_return_true_given_valid_dcv_with_caa_check_request(self):
        request = ValidRequestCreator.create_valid_dcv_with_caa_check_request()
        is_request_valid, validation_issues = MpicRequestValidator.is_request_valid(RequestPath.DCV_WITH_CAA_CHECK, request, self.known_perspectives)
        assert is_request_valid is True
        assert len(validation_issues) == 0

    @pytest.mark.parametrize('request_path', ['/invalid-path'])  # do any other path types need testing?
    def is_request_valid__should_return_false_and_message_given_unsupported_request_path(self, request_path):
        request = ValidRequestCreator.create_valid_caa_check_request()
        is_request_valid, validation_issues = MpicRequestValidator.is_request_valid(request_path, request, self.known_perspectives)
        assert is_request_valid is False
        assert ValidationMessages.UNSUPPORTED_REQUEST_PATH.key in [issue.issue_type for issue in validation_issues]
        unsupported_request_path_issue = next(issue for issue in validation_issues if issue.issue_type == ValidationMessages.UNSUPPORTED_REQUEST_PATH.key)
        assert request_path in unsupported_request_path_issue.message

    @pytest.mark.parametrize('perspective_count', [1, 0, -1, 'abc', sys.maxsize+1])
    def is_request_valid__should_return_false_and_message_given_invalid_perspective_count(self, perspective_count):
        request = ValidRequestCreator.create_valid_caa_check_request()
        request.orchestration_parameters.perspective_count = perspective_count
        is_request_valid, validation_issues = MpicRequestValidator.is_request_valid(RequestPath.CAA_CHECK, request, self.known_perspectives)
        assert is_request_valid is False
        assert ValidationMessages.INVALID_PERSPECTIVE_COUNT.key in [issue.issue_type for issue in validation_issues]
        invalid_perspective_count_issue = next(issue for issue in validation_issues if issue.issue_type == ValidationMessages.INVALID_PERSPECTIVE_COUNT.key)
        assert str(perspective_count) in invalid_perspective_count_issue.message

    # TODO discuss enforcement of 500km distance between perspective regions. (And 2+ RIR requirement.)
    def is_request_valid__should_return_false_and_message_given_invalid_perspective_list(self):
        request = ValidRequestCreator.create_valid_caa_check_request()
        request.orchestration_parameters.perspective_count = None
        request.orchestration_parameters.perspectives = ['bad_p1', 'bad_p2', 'bad_p3', 'bad_p4', 'bad_p5', 'bad_p6']
        is_request_valid, validation_issues = MpicRequestValidator.is_request_valid(RequestPath.CAA_CHECK, request, self.known_perspectives, True)
        assert is_request_valid is False
        assert ValidationMessages.INVALID_PERSPECTIVE_LIST.key in [issue.issue_type for issue in validation_issues]

    # TODO should there be a more permissive validation (in diagnostic mode?) for quorum count?
    @pytest.mark.parametrize('quorum_count', [1, -1, 10, 'abc', sys.maxsize+1])
    def is_request_valid__should_return_false_and_message_given_invalid_quorum_count(self, quorum_count):
        request = ValidRequestCreator.create_valid_caa_check_request()
        request.orchestration_parameters.quorum_count = quorum_count
        is_request_valid, validation_issues = MpicRequestValidator.is_request_valid(RequestPath.CAA_CHECK, request, self.known_perspectives)
        assert is_request_valid is False
        assert ValidationMessages.INVALID_QUORUM_COUNT.key in [issue.issue_type for issue in validation_issues]
        invalid_quorum_count_issue = next(issue for issue in validation_issues if issue.issue_type == ValidationMessages.INVALID_QUORUM_COUNT.key)
        assert str(quorum_count) in invalid_quorum_count_issue.message

    # TODO probably shouldn't allow a quorum count of zero, but that is an API spec update
    def is_request_valid__should_allow_quorum_count_of_zero(self):
        request = ValidRequestCreator.create_valid_caa_check_request()
        request.orchestration_parameters.quorum_count = 0
        is_request_valid, validation_issues = MpicRequestValidator.is_request_valid(RequestPath.CAA_CHECK, request, self.known_perspectives)
        assert is_request_valid is True
        assert len(validation_issues) == 0


if __name__ == '__main__':
    pytest.main()
