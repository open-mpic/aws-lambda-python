from aws_lambda_python.mpic_coordinator.domain.certificate_type import CertificateType
from aws_lambda_python.mpic_coordinator.domain.dcv_validation_method import DcvValidationMethod


class MpicRequestValidator:
    @staticmethod  # placeholder for future validation of request body
    #  returns a list of validation issues found in the request body; if empty, request body is valid
    def validate_request_body(request_path, request_body):
        request_body_validation_issues = []

        # enforce presence of required fields
        if 'api-version' not in request_body:
            request_body_validation_issues.append('missing-api-version')

        if 'system-params' not in request_body:
            request_body_validation_issues.append('missing-system-params')
        else:  # TODO rename 'identifier' to something more descriptive in the spec, then fix this error message
            if 'identifier' not in request_body['system-params']:
                request_body_validation_issues.append('missing-domain-or-ip-target')

            # enforce that only one of 'perspectives' or 'perspective-count' is present
            if 'perspectives' in request_body['system-params'] and 'perspective-count' in request_body['system-params']:
                request_body_validation_issues.append('contains-both-perspectives-and-perspective-count')

        # have a switch based on request path to enforce additional validation rules
        # for example, if request_path == '/caa-check', then enforce that 'caa-details' is present
        # and that 'validation-details' is not present
        match request_path:
            case '/caa-check':
                if 'caa-details' in request_body:
                    MpicRequestValidator.validate_caa_check_request_details(request_body, request_body_validation_issues)
            case '/validation':
                MpicRequestValidator.validate_dcv_check_request_details(request_body, request_body_validation_issues)

        # returns true if no validation issues found, false otherwise; includes list of validation issues found
        return len(request_body_validation_issues) == 0, request_body_validation_issues

    @staticmethod
    def validate_caa_check_request_details(request_body, request_body_validation_issues) -> None:
        if 'caa-details' in request_body:
            if 'certificate-type' not in request_body['caa-details']:
                request_body_validation_issues.append('missing-certificate-type-in-caa-details')
            else:
                # TODO is there a default certificate type we should use if not specified?
                certificate_type = request_body['caa-details']['certificate-type']
                # check if certificate_type is not in CertificateType enum
                if certificate_type not in iter(CertificateType):
                    request_body_validation_issues.append('invalid-certificate-type-in-caa-details')
                # TODO do we check anything as far as validity for caa-domains?

    @staticmethod
    def validate_dcv_check_request_details(request_body, request_body_validation_issues) -> None:
        # TODO should we return early upon finding any validation issue? or try to accumulate issues?
        # accumulating issues is more "helpful," but makes the validation logic a bit more clunky
        if 'validation-method' not in request_body:
            request_body_validation_issues.append('missing-validation-method')
        elif request_body['validation-method'] not in iter(DcvValidationMethod):
            request_body_validation_issues.append('invalid-validation-method')
        else:
            if 'validation-details' not in request_body:  # TODO should we enforce this for all methods?
                request_body_validation_issues.append('missing-validation-details')
            else:
                validation_details = request_body['validation-details']
                # TODO should we enforce expected_challenge everywhere? or is it not actually required?
                match request_body['validation-method']:
                    case DcvValidationMethod.DNS_GENERIC:
                        if 'prefix' not in validation_details:
                            request_body_validation_issues.append('missing-prefix-in-validation-details')
                        if 'record-type' not in validation_details:
                            request_body_validation_issues.append('missing-record-type-in-validation-details')
                        if 'expected-challenge' not in validation_details:
                            request_body_validation_issues.append('missing-expected-challenge-in-validation-details')
                    case DcvValidationMethod.HTTP_GENERIC:
                        if 'path' not in validation_details:
                            request_body_validation_issues.append('missing-path-in-validation-details')
                        if 'expected-challenge' not in validation_details:
                            request_body_validation_issues.append('missing-expected-challenge-in-validation-details')
                    case DcvValidationMethod.TLS_USING_ALPN:
                        if 'expected-challenge' not in validation_details:
                            request_body_validation_issues.append('missing-expected-challenge-in-validation-details')
