from enum import StrEnum


# TODO what DNS record types do we need to support?
class DnsRecordType(StrEnum):
    A = 'A record'
    AAAA = 'AAAA record'
    CAA = 'CAA record'
    CERT = 'CERT record'
    CNAME = 'CNAME record'
    DCHID = 'DCHID record'
    DNAME = 'DNAME record'
    DNSKEY = 'DNSKEY record'
    DS = 'DS record'
    HIP = 'HIP record'
    MX = 'MX record'
    NS = 'NS record'
    NSEC = 'NSEC record'
    PTR = 'PTR record'
    RP = 'RP record'
    RRSIG = 'RRSIG record'
    SOA = 'SOA record'
    SRV = 'SRV record'
    SSHFP = 'SSHFP record'
    TXT = 'TXT record'
