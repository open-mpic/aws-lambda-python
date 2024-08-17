from enum import StrEnum


class RequestPath(StrEnum):
    CAA_CHECK = '/caa-check'
    DCV_CHECK = '/validation'
    DCV_WITH_CAA_CHECK = '/validation-with-caa-check'
