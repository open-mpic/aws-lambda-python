import dns
from dns.flags import Flag
from dns.rdtypes.ANY.CAA import CAA
from dns.rdtypes.ANY.CNAME import CNAME
from dns.rdtypes.ANY.TXT import TXT
from dns.rrset import RRset

from open_mpic_core.common_domain.enum.dns_record_type import DnsRecordType


class MockDnsObjectCreator:
    @staticmethod
    def create_caa_rrset(*caa_records: CAA):
        test_rrset = RRset(name=dns.name.from_text('example.com'), rdclass=dns.rdataclass.IN, rdtype=dns.rdatatype.CAA)
        for caa_record in caa_records:
            test_rrset.add(caa_record)
        return test_rrset

    @staticmethod
    def create_caa_record(flags, tag, value):
        return MockDnsObjectCreator.create_record_by_type(DnsRecordType.CAA, {'flag': flags, 'tag': tag, 'value': value})

    @staticmethod
    def create_record_by_type(record_type, record_data):
        value = record_data['value']
        match record_type:
            case DnsRecordType.CNAME:
                return CNAME(dns.rdataclass.IN, dns.rdatatype.CNAME, target=value)
            case DnsRecordType.TXT:
                return TXT(dns.rdataclass.IN, dns.rdatatype.TXT, strings=[value.encode('utf-8')])
            case DnsRecordType.CAA:
                flags = record_data['flag']
                tag = record_data['tag']
                return CAA(dns.rdataclass.IN, dns.rdatatype.CAA, flags=flags, tag=tag.encode('utf-8'), value=value.encode('utf-8'))

    @staticmethod
    def create_caa_query_answer(record_name, flags, tag, value, mocker):
        return MockDnsObjectCreator.create_dns_query_answer(record_name, '', DnsRecordType.CAA,
                                                            {'flag': flags, 'tag': tag, 'value': value}, mocker)

    @staticmethod
    def create_dns_query_answer(record_name, record_name_prefix, record_type, record_data, mocker):
        dns_record = None
        match record_type:
            case DnsRecordType.CNAME:
                dns_record = MockDnsObjectCreator.create_record_by_type(DnsRecordType.CNAME, record_data)
            case DnsRecordType.TXT:
                dns_record = MockDnsObjectCreator.create_record_by_type(DnsRecordType.TXT, record_data)
            case DnsRecordType.CAA:
                dns_record = MockDnsObjectCreator.create_record_by_type(DnsRecordType.CAA, record_data)
        good_response = dns.message.QueryMessage()
        good_response.flags = Flag.QR | Flag.RD | Flag.RA
        if (record_name_prefix is not None) and (record_name_prefix != ''):  # if there is a domain name prefix
            dns_record_name = dns.name.from_text(f"{record_name_prefix}.{record_name}")  # domain name prefix + domain name
        else:
            dns_record_name = dns.name.from_text(record_name)
        dns_record_type = dns.rdatatype.from_text(record_type)
        response_question_rrset = RRset(name=dns_record_name, rdclass=dns.rdataclass.IN, rdtype=dns_record_type)
        good_response.question = [response_question_rrset]
        response_answer_rrset = RRset(name=dns_record_name, rdclass=dns.rdataclass.IN, rdtype=dns_record_type)
        response_answer_rrset.add(dns_record)
        good_response.answer = [response_answer_rrset]  # caa checker doesn't look here, but dcv checker does
        mocker.patch('dns.message.Message.find_rrset', return_value=response_answer_rrset)  # needed for Answer constructor to work
        return dns.resolver.Answer(qname=dns_record_name, rdtype=dns_record_type, rdclass=dns.rdataclass.IN, response=good_response)
