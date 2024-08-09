import numbers
import re
from aws_lambda_python.mpic_coordinator.domain.certificate_type import CertificateType
from aws_lambda_python.mpic_coordinator.domain.dcv_validation_method import DcvValidationMethod
from aws_lambda_python.mpic_coordinator.domain.request_paths import RequestPaths
from aws_lambda_python.mpic_coordinator.messages.validation_messages import ValidationMessages
from aws_lambda_python.mpic_coordinator.validation_issue import ValidationIssue


class MpicRequestValidator:
    @staticmethod
    # returns a list of validation issues found in the request body; if empty, request body is valid
    # TODO return upon finding first validation issue? or accumulate issues? accumulating is more "helpful" to caller
    def is_request_body_valid(request_path, request_body, known_perspectives) -> (bool, list):
        request_body_validation_issues = []

        # enforce presence of required fields
        if 'api-version' not in request_body:
            request_body_validation_issues.append(ValidationIssue(ValidationMessages.MISSING_API_VERSION))
        else:
            MpicRequestValidator.validate_api_version(request_body['api-version'], request_body_validation_issues)

        if 'system-params' not in request_body:
            request_body_validation_issues.append(ValidationIssue(ValidationMessages.MISSING_SYSTEM_PARAMS))
        else:  # TODO rename 'identifier' to something more descriptive in the spec, then fix this error message
            if 'identifier' not in request_body['system-params']:
                request_body_validation_issues.append(ValidationIssue(ValidationMessages.MISSING_DOMAIN_OR_IP_TARGET))

            # enforce that only one of 'perspectives' or 'perspective-count' is present
            if 'perspectives' in request_body['system-params'] and 'perspective-count' in request_body['system-params']:
                request_body_validation_issues.append(ValidationIssue(ValidationMessages.PERSPECTIVES_WITH_PERSPECTIVE_COUNT))
            elif 'perspectives' in request_body['system-params']:
                requested_perspectives = request_body['system-params']['perspectives']
                MpicRequestValidator.validate_requested_perspectives(requested_perspectives, known_perspectives, request_body_validation_issues)
            elif 'perspective-count' in request_body['system-params']:
                requested_perspective_count = request_body['system-params']['perspective-count']
                MpicRequestValidator.validate_requested_perspective_count(requested_perspective_count, known_perspectives, request_body_validation_issues)

        # have a switch based on request path to enforce additional validation rules
        # for example, if request_path == '/caa-check', then enforce that 'caa-details' is present
        # and that 'validation-details' is not present
        match request_path:
            case RequestPaths.CAA_CHECK | RequestPaths.DCV_WITH_CAA_CHECK:
                if 'caa-details' in request_body:
                    MpicRequestValidator.validate_caa_check_request_details(request_body, request_body_validation_issues)
            case RequestPaths.DCV_CHECK | RequestPaths.DCV_WITH_CAA_CHECK:
                MpicRequestValidator.validate_dcv_check_request_details(request_body, request_body_validation_issues)
            case _:
                request_body_validation_issues.append(ValidationIssue(ValidationMessages.UNSUPPORTED_REQUEST_PATH, request_path))

        # returns true if no validation issues found, false otherwise; includes list of validation issues found
        return len(request_body_validation_issues) == 0, request_body_validation_issues

    @staticmethod
    def validate_caa_check_request_details(request_body, request_body_validation_issues) -> None:
        if 'caa-details' in request_body:
            if 'certificate-type' in request_body['caa-details']:
                certificate_type = request_body['caa-details']['certificate-type']
                # check if certificate_type is not in CertificateType enum
                if certificate_type not in iter(CertificateType):
                    request_body_validation_issues.append(ValidationIssue(ValidationMessages.INVALID_CERTIFICATE_TYPE, certificate_type))
                # TODO do we check anything as far as validity for caa-domains?

    @staticmethod
    def validate_dcv_check_request_details(request_body, request_body_validation_issues) -> None:
        if 'validation-method' not in request_body:
            request_body_validation_issues.append(ValidationIssue(ValidationMessages.MISSING_VALIDATION_METHOD))
        elif request_body['validation-method'] not in iter(DcvValidationMethod):
            bad_validation_method = request_body['validation-method']
            request_body_validation_issues.append(ValidationIssue(ValidationMessages.INVALID_VALIDATION_METHOD, bad_validation_method))
        else:
            if 'validation-details' not in request_body:  # TODO should we enforce this for all methods?
                request_body_validation_issues.append(ValidationIssue(ValidationMessages.MISSING_VALIDATION_DETAILS))
            else:
                validation_details = request_body['validation-details']
                # TODO should we enforce expected_challenge everywhere? or is it not actually required?
                match request_body['validation-method']:
                    case DcvValidationMethod.DNS_GENERIC:
                        if 'prefix' not in validation_details:
                            request_body_validation_issues.append(ValidationIssue(ValidationMessages.MISSING_PREFIX, DcvValidationMethod.DNS_GENERIC))
                        if 'record-type' not in validation_details:
                            request_body_validation_issues.append(ValidationIssue(ValidationMessages.MISSING_RECORD_TYPE, DcvValidationMethod.DNS_GENERIC))
                        if 'expected-challenge' not in validation_details:
                            request_body_validation_issues.append(ValidationIssue(ValidationMessages.MISSING_EXPECTED_CHALLENGE, DcvValidationMethod.DNS_GENERIC))
                    case DcvValidationMethod.HTTP_GENERIC:
                        if 'path' not in validation_details:
                            request_body_validation_issues.append(ValidationIssue(ValidationMessages.MISSING_PATH, DcvValidationMethod.HTTP_GENERIC))
                        if 'expected-challenge' not in validation_details:
                            request_body_validation_issues.append(ValidationIssue(ValidationMessages.MISSING_EXPECTED_CHALLENGE, DcvValidationMethod.HTTP_GENERIC))
                    case DcvValidationMethod.TLS_USING_ALPN:
                        if 'expected-challenge' not in validation_details:
                            request_body_validation_issues.append(ValidationIssue(ValidationMessages.MISSING_EXPECTED_CHALLENGE, DcvValidationMethod.TLS_USING_ALPN))

    @staticmethod
    def validate_api_version(api_version, request_body_validation_issues) -> None:
        # check if api_version matches regex pattern for API versions that look like 1.0.0
        if not re.match(r'^\d+(\.\d+)+$', api_version):
            request_body_validation_issues.append(ValidationIssue(ValidationMessages.INVALID_API_VERSION, api_version))
        else:
            request_api_major_version = api_version.split('.')
            if int(request_api_major_version[0]) != 1:
                request_body_validation_issues.append(ValidationIssue(ValidationMessages.INVALID_API_VERSION, api_version))

    @staticmethod
    def validate_requested_perspectives(requested_perspectives, known_perspectives, request_body_validation_issues) -> None:
        # check if requested_perspectives is a subset of known_perspectives
        if not all(perspective in known_perspectives for perspective in requested_perspectives):
            request_body_validation_issues.append(ValidationIssue(ValidationMessages.INVALID_PERSPECTIVE_LIST))

    @staticmethod
    def validate_requested_perspective_count(requested_perspective_count, known_perspectives, request_body_validation_issues) -> None:
        # check if requested_perspective_count is an integer, at least 2, and at most the number of known_perspectives
        if not (isinstance(requested_perspective_count, int) and 2 <= requested_perspective_count <= len(known_perspectives)):
            request_body_validation_issues.append(ValidationIssue(ValidationMessages.INVALID_PERSPECTIVE_COUNT, requested_perspective_count))
