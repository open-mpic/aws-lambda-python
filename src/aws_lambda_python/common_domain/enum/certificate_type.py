from enum import StrEnum


class CertificateType(StrEnum):
    TLS_SERVER = 'tls-server'
    TLS_SERVER_WILDCARD = 'tls-server:wildcard'
    S_MIME = 's-mime'
