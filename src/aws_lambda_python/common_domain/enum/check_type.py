from enum import StrEnum


class CheckType(StrEnum):
    CAA = 'caa'
    DCV = 'dcv'
    DCV_WITH_CAA = 'dcv_with_caa'
