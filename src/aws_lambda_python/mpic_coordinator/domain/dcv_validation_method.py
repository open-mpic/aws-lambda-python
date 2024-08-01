from enum import StrEnum


class DcvValidationMethod(StrEnum):
    HTTP_GENERIC = 'http-generic'
    DNS_GENERIC = 'dns-generic'
    TLS_USING_ALPN = 'tls-using-alpn'
