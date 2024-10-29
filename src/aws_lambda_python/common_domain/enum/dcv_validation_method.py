from enum import StrEnum


class DcvValidationMethod(StrEnum):
    HTTP_GENERIC = 'http-generic'  # TODO rename to something better
    DNS_GENERIC = 'dns-generic'  # TODO rename to something better
    # ACME = 'acme'  # TODO implement ACME validation... and later TLS_USING_ALPN
