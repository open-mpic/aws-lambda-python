from enum import StrEnum


class DcvValidationMethod(StrEnum):
    HTTP_GENERIC = 'http-generic'  # TODO rename to something better
    DNS_GENERIC = 'dns-generic'  # TODO rename to something better
    # WEBSITE_CHANGE_V2 = 'website-change-v2'  # HTTP (need to specify if HTTP or HTTPS)
    # ACME_V2_HTTP_01 = 'acme-v2-http-01'
    # ACME_V2_DNS_01 = 'acme-v2-dns-01'
    # ACME_V2_TLS_ALP_N01 = 'acme-v2-tls-alpn-01'
    # DNS_CHANGE = 'dns-change'
