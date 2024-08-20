import re

from aws_lambda_python.mpic_coordinator.config.service_config import API_VERSION
from aws_lambda_python.common_domain.certificate_type import CertificateType
from aws_lambda_python.common_domain.dcv_validation_method import DcvValidationMethod
from aws_lambda_python.mpic_coordinator.domain.mpic_request import MpicRequest
from aws_lambda_python.mpic_coordinator.domain.request_path import RequestPath
from aws_lambda_python.mpic_coordinator.messages.validation_messages import ValidationMessages
from aws_lambda_python.mpic_coordinator.validation_issue import ValidationIssue


class MpicRequestValidator:
    @staticmethod
    # returns a list of validation issues found in the request; if empty, request is (probably) valid
    # TODO should we create a flag to validate values separately from structure?
    def is_request_valid(request_path, mpic_request: MpicRequest, known_perspectives, diagnostic_mode=False) -> (bool, list):
        request_validation_issues = []

        # TODO if API version is in the URL then we don't need to validate it here explicitly
        if mpic_request.api_version is None:
            request_validation_issues.append(ValidationIssue(ValidationMessages.MISSING_API_VERSION))
        else:
            MpicRequestValidator.validate_api_version(mpic_request.api_version, request_validation_issues)

        if mpic_request.system_params is None:
            request_validation_issues.append(ValidationIssue(ValidationMessages.MISSING_SYSTEM_PARAMS))
        else:
            if mpic_request.system_params.domain_or_ip_target is None:
                request_validation_issues.append(ValidationIssue(ValidationMessages.MISSING_DOMAIN_OR_IP_TARGET))

            # TODO align on this: if present, should 'perspectives' override 'perspective-count'? or conflict?
            # 'perspectives' is allowed if 'diagnostic_mode' is True
            # if 'diagnostic-mode' is false, 'perspectives' is not allowed
            # enforce that only one of 'perspectives' or 'perspective-count' is present
            if (mpic_request.system_params.perspectives is not None and
                    mpic_request.system_params.perspective_count is not None):
                request_validation_issues.append(ValidationIssue(ValidationMessages.PERSPECTIVES_WITH_PERSPECTIVE_COUNT))
            else:
                should_validate_quorum_count = False
                requested_perspective_count = 0
                if mpic_request.system_params.perspectives is not None:
                    requested_perspectives = mpic_request.system_params.perspectives
                    requested_perspective_count = len(requested_perspectives)
                    if MpicRequestValidator.are_requested_perspectives_valid(requested_perspectives, known_perspectives):
                        should_validate_quorum_count = True
                    else:
                        request_validation_issues.append(ValidationIssue(ValidationMessages.INVALID_PERSPECTIVE_LIST))
                elif mpic_request.system_params.perspective_count is not None:
                    requested_perspective_count = mpic_request.system_params.perspective_count
                    if MpicRequestValidator.is_requested_perspective_count_valid(requested_perspective_count, known_perspectives):
                        should_validate_quorum_count = True
                    else:
                        request_validation_issues.append(ValidationIssue(ValidationMessages.INVALID_PERSPECTIVE_COUNT, requested_perspective_count))
                if should_validate_quorum_count and mpic_request.system_params.quorum_count is not None:
                    quorum_count = mpic_request.system_params.quorum_count
                    MpicRequestValidator.validate_quorum_count(requested_perspective_count, quorum_count, request_validation_issues)

        # enforce additional validation rules based on request path
        match request_path:
            case RequestPath.CAA_CHECK:
                if mpic_request.caa_details is not None:
                    MpicRequestValidator.validate_mpic_request_caa_check_details(mpic_request, request_validation_issues)
            case RequestPath.DCV_CHECK:
                MpicRequestValidator.validate_mpic_request_dcv_check_details(mpic_request, request_validation_issues)
            case RequestPath.DCV_WITH_CAA_CHECK:
                if mpic_request.caa_details is not None:
                    MpicRequestValidator.validate_mpic_request_caa_check_details(mpic_request, request_validation_issues)
                MpicRequestValidator.validate_mpic_request_dcv_check_details(mpic_request, request_validation_issues)
            case _:
                request_validation_issues.append(
                    ValidationIssue(ValidationMessages.UNSUPPORTED_REQUEST_PATH, request_path))

        # returns true if no validation issues found, false otherwise; includes list of validation issues found
        return len(request_validation_issues) == 0, request_validation_issues

    @staticmethod  # TODO remove this method if we move API version to the URL
    def validate_api_version(api_version, request_validation_issues) -> None:
        # follow SemVer guidelines: https://semver.org/ (major version, minor version, patch version)
        # check if api_version matches regex pattern for API versions that look like 1.0.0
        if not re.match(r'^\d+(\.\d+)+$', api_version):
            request_validation_issues.append(ValidationIssue(ValidationMessages.INVALID_API_VERSION, api_version))
        else:
            current_api_major_version = API_VERSION.split('.')[0]
            request_api_major_version = api_version.split('.')[0]
            if int(request_api_major_version) != int(current_api_major_version):  # check if major version is 1; ignore minor and patch versions
                request_validation_issues.append(ValidationIssue(ValidationMessages.INVALID_API_VERSION, api_version))

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
            request_validation_issues.append(ValidationIssue(ValidationMessages.INVALID_QUORUM_COUNT, quorum_count))

    @staticmethod
    def validate_mpic_request_caa_check_details(mpic_request: MpicRequest, request_validation_issues) -> None:
        if mpic_request.caa_details is not None:
            if mpic_request.caa_details.certificate_type is not None:
                certificate_type = mpic_request.caa_details.certificate_type
                # check if certificate_type is not in CertificateType enum
                if certificate_type not in iter(CertificateType):
                    request_validation_issues.append(ValidationIssue(ValidationMessages.INVALID_CERTIFICATE_TYPE, certificate_type))
                # TODO do we check anything as far as validity for caa-domains?

    @staticmethod
    def validate_mpic_request_dcv_check_details(mpic_request: MpicRequest, request_validation_issues) -> None:
        if mpic_request.validation_method is None:
            request_validation_issues.append(ValidationIssue(ValidationMessages.MISSING_VALIDATION_METHOD))
        elif mpic_request.validation_method not in iter(DcvValidationMethod):
            request_validation_issues.append(ValidationIssue(ValidationMessages.INVALID_VALIDATION_METHOD, mpic_request.validation_method))

        if mpic_request.validation_details is None:  # TODO should we enforce this for all methods?
            request_validation_issues.append(ValidationIssue(ValidationMessages.MISSING_VALIDATION_DETAILS))
        else:
            # TODO should we enforce expected_challenge everywhere? or is it not actually required?
            match mpic_request.validation_method:
                case DcvValidationMethod.DNS_GENERIC:
                    if mpic_request.validation_details.prefix is None:
                        request_validation_issues.append(ValidationIssue(ValidationMessages.MISSING_PREFIX, DcvValidationMethod.DNS_GENERIC))
                    if mpic_request.validation_details.record_type is None:
                        request_validation_issues.append(ValidationIssue(ValidationMessages.MISSING_RECORD_TYPE, DcvValidationMethod.DNS_GENERIC))
                    if mpic_request.validation_details.expected_challenge is None:
                        request_validation_issues.append(ValidationIssue(ValidationMessages.MISSING_EXPECTED_CHALLENGE, DcvValidationMethod.DNS_GENERIC))
                case DcvValidationMethod.HTTP_GENERIC:
                    if mpic_request.validation_details.path is None:
                        request_validation_issues.append(ValidationIssue(ValidationMessages.MISSING_PATH, DcvValidationMethod.HTTP_GENERIC))
                    if mpic_request.validation_details.expected_challenge is None:
                        request_validation_issues.append(ValidationIssue(ValidationMessages.MISSING_EXPECTED_CHALLENGE, DcvValidationMethod.HTTP_GENERIC))
                # TODO should we remove TLS_USING_ALPN method from this version of the API?
                case DcvValidationMethod.TLS_USING_ALPN:
                    if mpic_request.validation_details.expected_challenge is None:
                        request_validation_issues.append(ValidationIssue(ValidationMessages.MISSING_EXPECTED_CHALLENGE, DcvValidationMethod.TLS_USING_ALPN))
