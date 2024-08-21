from enum import Enum


class ValidationMessages(Enum):
    MISSING_API_VERSION = ("missing-api-version", "Missing 'api-version' in request.")
    INVALID_API_VERSION = ("invalid-api-version", "Invalid 'api-version' specified: {0}")
    UNSUPPORTED_REQUEST_PATH = ("unsupported-request-path", "Unsupported request path: {0}")
    MISSING_SYSTEM_PARAMS = ("missing-system-params", "Missing 'system-params' in request.")
    MISSING_DOMAIN_OR_IP_TARGET = ("missing-domain-or-ip-target", "Missing 'domain-or-ip-target' in 'system-params'.")
    PERSPECTIVES_WITH_PERSPECTIVE_COUNT = ("contains-both-perspectives-and-perspective-count", "Request contains both 'perspectives' and 'perspective-count'.")
    INVALID_PERSPECTIVE_COUNT = ("invalid-perspective-count", "Invalid perspective count: {0}")
    INVALID_PERSPECTIVE_LIST = ("invalid-perspective-list", "Invalid perspective list specified.")
    PERSPECTIVES_NOT_IN_DIAGNOSTIC_MODE = ("perspectives-not-in-diagnostic-mode", "Explicitly listing perspectives is only allowed in diagnostics mode.")
    INVALID_QUORUM_COUNT = ("invalid-quorum-count", "Invalid quorum count: {0}")
    INVALID_CERTIFICATE_TYPE = ("invalid-certificate-type", "Invalid 'certificate-type' specified: {0}")
    MISSING_VALIDATION_METHOD = ("missing-validation-method", "Missing 'validation-method' for DCV.")
    INVALID_VALIDATION_METHOD = ("invalid-validation-method", "Invalid 'validation-method' specified: {0}")
    MISSING_VALIDATION_DETAILS = ("missing-validation-details", "Missing 'validation-details' for DCV.")
    MISSING_EXPECTED_CHALLENGE = ("missing-expected-challenge", "Missing 'expected-challenge' in validation details for {0}.")
    MISSING_PREFIX = ("missing-prefix", "Missing 'prefix' in validation details for DNS validation.")
    MISSING_RECORD_TYPE = ("missing-record-type", "Missing 'record-type' in validation details for DNS validation.")
    MISSING_PATH = ("missing-path", "Missing 'path' in validation details for HTTP validation.")
    REQUEST_VALIDATION_FAILED = ("request-validation-failed", "Request validation failed.")

    def __init__(self, key, message):
        self.key = key
        self.message = message
