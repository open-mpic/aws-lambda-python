from enum import Enum


class MpicRequestValidationMessages(Enum):
    UNSUPPORTED_REQUEST_PATH = ("unsupported-request-path", "Unsupported request path: {0}")
    PERSPECTIVES_WITH_PERSPECTIVE_COUNT = ("contains-both-perspectives-and-perspective-count", "Request contains both 'perspectives' and 'perspective-count'.")
    INVALID_PERSPECTIVE_COUNT = ("invalid-perspective-count", "Invalid perspective count: {0}")
    INVALID_PERSPECTIVE_LIST = ("invalid-perspective-list", "Invalid perspective list specified.")
    PERSPECTIVES_NOT_IN_DIAGNOSTIC_MODE = ("perspectives-not-in-diagnostic-mode", "Explicitly listing perspectives is only allowed in diagnostics mode.")
    INVALID_QUORUM_COUNT = ("invalid-quorum-count", "Invalid quorum count: {0}")
    INVALID_CERTIFICATE_TYPE = ("invalid-certificate-type", "Invalid 'certificate-type' specified: {0}")
    INVALID_VALIDATION_METHOD = ("invalid-validation-method", "Invalid 'validation-method' specified: {0}")
    REQUEST_VALIDATION_FAILED = ("request-validation-failed", "Request validation failed.")

    def __init__(self, key, message):
        self.key = key
        self.message = message
