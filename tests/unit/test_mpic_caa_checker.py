import dns
import pytest
from aws_lambda_python.mpic_caa_checker.mpic_caa_checker import MpicCaaChecker
from dns.rdtypes.ANY.CAA import CAA
from dns.rrset import RRset

CAA_RDCLASS = dns.rdataclass.IN
CAA_RDTYPE = dns.rdatatype.CAA


# noinspection PyMethodMayBeStatic
class TestMpicCaaChecker:
    @pytest.fixture
    def rrset(self):
        caa_rdata_1 = CAA(CAA_RDCLASS, CAA_RDTYPE, flags=0, tag=b'issue', value=b'ca1.org')
        caa_rdata_2 = CAA(CAA_RDCLASS, CAA_RDTYPE, flags=0, tag=b'issue', value=b'ca2.org')
        rrset = RRset(name=dns.name.Name('example'), rdclass=CAA_RDCLASS, rdtype=CAA_RDTYPE)
        rrset.add(caa_rdata_1)
        rrset.add(caa_rdata_2)
        return rrset

    @pytest.mark.parametrize('value_list, caa_domains', [
        (['ca1.org'], ['ca1.org']),
        (['ca1.org', 'ca2.com'], ['ca2.com']),
        (['ca1.org', 'ca2.com'], ['ca3.org', 'ca1.org']),
    ])
    def does_value_list_permit_issuance__should_return_true_given_one_value_found_in_caa_domains(self, value_list, caa_domains):
        result = MpicCaaChecker.does_value_list_permit_issuance(value_list, caa_domains)
        assert result is True

    def does_value_list_permit_issuance__should_return_false_given_value_not_found_in_caa_domains(self):
        value_list = ['letsencrypt.org']
        caa_domains = ['google.com']
        result = MpicCaaChecker.does_value_list_permit_issuance(value_list, caa_domains)
        assert result is False

    def does_value_list_permit_issuance__should_return_false_given_only_values_with_extensions(self):
        value_list = ['0 issue "letsencrypt.org; policy=ev"']
        caa_domains = ['letsencrypt.org']
        result = MpicCaaChecker.does_value_list_permit_issuance(value_list, caa_domains)
        assert result is False

    def does_value_list_permit_issuance__should_ignore_whitespace_around_values(self):
        value_list = ['  ca1.org  ']
        caa_domains = ['ca1.org']
        result = MpicCaaChecker.does_value_list_permit_issuance(value_list, caa_domains)
        assert result is True

    def is_valid_for_issuance__should_return_true_given_rrset_contains_domain(self, rrset):
        caa_domains = ['ca1000.org']
        is_wc_domain = False
        rrset.add(CAA(CAA_RDCLASS, CAA_RDTYPE, flags=0, tag=b'issue', value=caa_domains[0].encode('utf-8')))
        result = MpicCaaChecker.is_valid_for_issuance(caa_domains, is_wc_domain, rrset)
        assert result is True

    def is_valid_for_issuance__should_return_true_given_rrset_contains_domain_and_domain_is_wildcard(self, rrset):
        caa_domains = ['ca1000.org']
        is_wc_domain = True
        rrset.add(CAA(CAA_RDCLASS, CAA_RDTYPE, flags=0, tag=b'issue', value=caa_domains[0].encode('utf-8')))
        result = MpicCaaChecker.is_valid_for_issuance(caa_domains, is_wc_domain, rrset)
        assert result is True

    def is_valid_for_issuance__should_return_true_given_rrset_contains_domain_with_issuewild_tag_and_domain_is_wildcard(self, rrset):
        caa_domains = ['ca1000.org']
        caa_rdata = CAA(CAA_RDCLASS, CAA_RDTYPE, flags=0, tag=b'issuewild', value=caa_domains[0].encode('utf-8'))
        rrset.add(caa_rdata)
        is_wc_domain = True
        result = MpicCaaChecker.is_valid_for_issuance(caa_domains, is_wc_domain, rrset)
        assert result is True

    def is_valid_for_issuance_should_return_false_given_rrset_contains_domain_with_issuewild_tag_and_domain_is_not_wildcard(self, rrset):
        caa_domains = ['ca1000.org']
        caa_rdata = CAA(CAA_RDCLASS, CAA_RDTYPE, flags=0, tag=b'issuewild', value=caa_domains[0].encode('utf-8'))
        rrset.add(caa_rdata)
        is_wc_domain = False
        result = MpicCaaChecker.is_valid_for_issuance(caa_domains, is_wc_domain, rrset)
        assert result is False

    #  TODO figure out if check for critical flag should override checks for issue and issuewild
    @pytest.mark.parametrize('caa_domain, rr_domain', [('ca1111.org', 'ca1111.org'), ('ca1111.org', 'ca2222.com')])
    def is_valid_for_issuance__should_return_false_given_rrset_contains_any_records_with_critical_flags(self, rrset, caa_domain, rr_domain):
        caa_domains = [caa_domain]
        caa_rdata = CAA(CAA_RDCLASS, CAA_RDTYPE, flags=128, tag=b'unknown', value=rr_domain.encode('utf-8'))
        rrset.add(caa_rdata)
        is_wc_domain = False
        result = MpicCaaChecker.is_valid_for_issuance(caa_domains, is_wc_domain, rrset)
        assert result is False


if __name__ == '__main__':
    pytest.main()
