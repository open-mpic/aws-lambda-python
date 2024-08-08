from enum import Enum


class ValidationMessages(Enum):
    MISSING_API_VERSION = ("missing-api-version", "Missing API version in request.")
    INVALID_API_VERSION = ("invalid-api-version", "Invalid API version specified: {0}")
    # TODO the ones below were auto-added by copilot, replace them once this is all working
    INVALID_QUORUM_COUNT = ("invalid_quorum_count", "Invalid quorum count: {0}")
    MISSING_CERTIFICATE_TYPE = ("missing_certificate_type", "Missing certificate type in CAA details.")
    INVALID_CERTIFICATE_TYPE = ("invalid_certificate_type", "Invalid certificate type specified: {0}")
    MISSING_VALIDATION_METHOD = ("missing_validation_method", "Missing validation method for DCV.")
    INVALID_VALIDATION_METHOD = ("invalid_validation_method", "Invalid validation method specified: {0}")
    MISSING_VALIDATION_DETAILS = ("missing_validation_details", "Missing validation details for DCV.")
    MISSING_EXPECTED_CHALLENGE = ("missing_expected_challenge", "Missing expected challenge in validation details for {0}.")
    MISSING_PREFIX = ("missing_prefix", "Missing prefix in validation details for DNS validation.")
    MISSING_RECORD_TYPE = ("missing_record_type", "Missing record type in validation details for DNS validation.")
    MISSING_PATH = ("missing_path", "Missing path in validation details for HTTP validation.")

    def __init__(self, key, message):
        self.key = key
        self.message = message
