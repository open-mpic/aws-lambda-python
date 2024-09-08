from enum import StrEnum


class DnsRecordType(StrEnum):
    A = 'A'
    AAAA = 'AAAA'
    CAA = 'CAA'
    CNAME = 'CNAME'
    TXT = 'TXT'
