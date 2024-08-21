from enum import StrEnum


class RequestPath(StrEnum):
    CAA_CHECK = '/caa-check'  # TODO replace with '/caa'?
    DCV_CHECK = '/validation'  # TODO replace with '/dcv'?
    DCV_WITH_CAA_CHECK = '/validation-with-caa-check'  # TODO replace with '/dcv-with-caa'?
