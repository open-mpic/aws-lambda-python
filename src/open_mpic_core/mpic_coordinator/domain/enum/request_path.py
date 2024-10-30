from enum import StrEnum


class RequestPath(StrEnum):
    """
    Enum for request path; only allows one value: /mpic
    """
    MPIC = '/mpic'
