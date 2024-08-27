from aws_lambda_python.mpic_coordinator.domain.enum.request_path import RequestPath
from aws_lambda_python.mpic_coordinator.messages.mpic_request_validation_messages import MpicRequestValidationMessages
from aws_lambda_python.mpic_coordinator.mpic_request_validation_issue import MpicRequestValidationIssue


# TODO rename to reflect that it's validating values rather than structure?
class MpicRequestValidator:
    @staticmethod
    # returns a list of validation issues found in the request; if empty, request is (probably) valid
    # TODO should we create a flag to validate values separately from structure?
    def is_request_valid(request_path, mpic_request, known_perspectives, diagnostic_mode=False) -> (bool, list):
        request_validation_issues = []

        # TODO align on this: if present, should 'perspectives' override 'perspective-count'? or conflict?
        # 'perspectives' is allowed if 'diagnostic_mode' is True
        # if 'diagnostic-mode' is false, 'perspectives' is not allowed
        # enforce that only one of 'perspectives' or 'perspective-count' is present
        should_validate_quorum_count = False
        requested_perspective_count = 0
        if mpic_request.orchestration_parameters.perspectives is not None and diagnostic_mode:
            requested_perspectives = mpic_request.orchestration_parameters.perspectives
            requested_perspective_count = len(requested_perspectives)
            if MpicRequestValidator.are_requested_perspectives_valid(requested_perspectives, known_perspectives):
                should_validate_quorum_count = True
            else:
                request_validation_issues.append(MpicRequestValidationIssue(MpicRequestValidationMessages.INVALID_PERSPECTIVE_LIST))
        elif mpic_request.orchestration_parameters.perspectives:
            request_validation_issues.append(MpicRequestValidationIssue(MpicRequestValidationMessages.PERSPECTIVES_NOT_IN_DIAGNOSTIC_MODE))
        elif mpic_request.orchestration_parameters.perspective_count is not None:
            requested_perspective_count = mpic_request.orchestration_parameters.perspective_count
            if MpicRequestValidator.is_requested_perspective_count_valid(requested_perspective_count, known_perspectives):
                should_validate_quorum_count = True
            else:
                request_validation_issues.append(MpicRequestValidationIssue(MpicRequestValidationMessages.INVALID_PERSPECTIVE_COUNT, requested_perspective_count))
        if should_validate_quorum_count and mpic_request.orchestration_parameters.quorum_count is not None:
            quorum_count = mpic_request.orchestration_parameters.quorum_count
            MpicRequestValidator.validate_quorum_count(requested_perspective_count, quorum_count, request_validation_issues)

        # TODO this should be checked in routing logic way before it gets here
        # check if request_path is supported in RequestPath enum
        if request_path not in iter(RequestPath):
            request_validation_issues.append(MpicRequestValidationIssue(MpicRequestValidationMessages.UNSUPPORTED_REQUEST_PATH, request_path))

        # returns true if no validation issues found, false otherwise; includes list of validation issues found
        return len(request_validation_issues) == 0, request_validation_issues

    @staticmethod
    def are_requested_perspectives_valid(requested_perspectives, known_perspectives) -> bool:
        # check if requested_perspectives is a subset of known_perspectives
        return all(perspective in known_perspectives for perspective in requested_perspectives)

    @staticmethod
    def is_requested_perspective_count_valid(requested_perspective_count, known_perspectives) -> bool:
        # check if requested_perspective_count is an integer, at least 2, and at most the number of known_perspectives
        return isinstance(requested_perspective_count, int) and 2 <= requested_perspective_count <= len(known_perspectives)

    @staticmethod
    def validate_quorum_count(requested_perspective_count, quorum_count, request_validation_issues) -> None:
        # quorum_count of 0 is OK; it signals log-only mode
        # quorum_count can be no less than perspectives-1 if perspectives <= 5
        # quorum_count can be no less than perspectives-2 if perspectives > 5
        quorum_is_valid = (isinstance(quorum_count, int) and (
                            quorum_count == 0 or
                            (requested_perspective_count - 1 <= quorum_count <= requested_perspective_count <= 5) or
                            (4 <= requested_perspective_count - 2 <= quorum_count <= requested_perspective_count)
                          ))
        if not quorum_is_valid:
            request_validation_issues.append(MpicRequestValidationIssue(MpicRequestValidationMessages.INVALID_QUORUM_COUNT, quorum_count))
