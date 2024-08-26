from enum import StrEnum


class DcvValidationMethod(StrEnum):
    HTTP_GENERIC = 'http-generic'  # TODO rename to something better
    DNS_GENERIC = 'dns-generic'  # TODO rename to something better
    TLS_USING_ALPN = 'tls-using-alpn'  # TODO remove unless it's supported (is it supported?)
