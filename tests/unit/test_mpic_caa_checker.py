import json

import dns
import pytest
from aws_lambda_python.common_domain.check_parameters import CaaCheckParameters
from aws_lambda_python.common_domain.check_request import CaaCheckRequest
from aws_lambda_python.common_domain.check_response import CaaCheckResponse, CaaCheckResponseDetails
from aws_lambda_python.common_domain.enum.certificate_type import CertificateType
from aws_lambda_python.mpic_caa_checker.mpic_caa_checker import MpicCaaChecker
from dns.flags import Flag
from dns.rdtypes.ANY.CAA import CAA
from dns.rrset import RRset

CAA_RDCLASS = dns.rdataclass.IN
CAA_RDTYPE = dns.rdatatype.CAA


# noinspection PyMethodMayBeStatic
class TestMpicCaaChecker:
    @staticmethod
    @pytest.fixture(scope='class')
    def set_env_variables():
        envvars = {
            'default_caa_domains': 'ca1.com|ca2.net|ca3.org',
            'AWS_REGION': 'us-east-4',
        }
        with pytest.MonkeyPatch.context() as class_scoped_monkeypatch:
            for k, v in envvars.items():
                class_scoped_monkeypatch.setenv(k, v)
            yield class_scoped_monkeypatch  # restore the environment afterward

    @pytest.fixture
    def test_rrset(self):
        caa_rdata_1 = CAA(CAA_RDCLASS, CAA_RDTYPE, flags=0, tag=b'issue', value=b'ca1.org')
        caa_rdata_2 = CAA(CAA_RDCLASS, CAA_RDTYPE, flags=0, tag=b'issue', value=b'ca2.org')
        rrset = RRset(name=dns.name.from_text('example.com'), rdclass=CAA_RDCLASS, rdtype=CAA_RDTYPE)
        rrset.add(caa_rdata_1)
        rrset.add(caa_rdata_2)
        return rrset

    @staticmethod
    def create_dns_query_answer(domain, ca_name, tag, mocker):
        caa_rdata_1 = CAA(CAA_RDCLASS, CAA_RDTYPE, flags=0, tag=tag.encode('utf-8'), value=ca_name.encode('utf-8'))
        good_response = dns.message.QueryMessage()
        good_response.flags = Flag.QR | Flag.RD | Flag.RA
        response_question_rrset = RRset(name=dns.name.from_text(domain), rdclass=CAA_RDCLASS, rdtype=CAA_RDTYPE)
        good_response.question = [response_question_rrset]
        response_answer_rrset = RRset(name=dns.name.from_text(domain), rdclass=CAA_RDCLASS, rdtype=CAA_RDTYPE)
        response_answer_rrset.add(caa_rdata_1)
        mocker.patch('dns.message.Message.find_rrset', return_value=response_answer_rrset)
        return dns.resolver.Answer(qname=dns.name.from_text(domain), rdtype=CAA_RDTYPE, rdclass=CAA_RDCLASS, response=good_response)

    # integration test of a sort -- only mocking dns methods rather than remaining class methods
    def check_caa__should_return_200_and_allow_issuance_given_no_caa_records_found(self, set_env_variables, mocker):
        mocker.patch('dns.resolver.resolve', side_effect=lambda domain_name, rdtype: exec('raise(dns.resolver.NoAnswer)'))
        caa_request = CaaCheckRequest(domain_or_ip_target='example.com',
                                      caa_check_parameters=CaaCheckParameters(certificate_type=CertificateType.TLS_SERVER, caa_domains=['ca111.com']))
        caa_checker = MpicCaaChecker()
        result = caa_checker.check_caa(caa_request)
        assert result['statusCode'] == 200
        check_response_details = CaaCheckResponseDetails(present=False)
        assert self.is_result_as_expected(result, True, check_response_details) is True

    def check_caa__should_return_200_and_allow_issuance_given_matching_caa_record_found(self, set_env_variables, mocker):
        test_dns_query_answer = TestMpicCaaChecker.create_dns_query_answer('example.com', 'ca111.com', 'issue', mocker)
        mocker.patch('dns.resolver.resolve', side_effect=lambda domain_name, rdtype: (
            test_dns_query_answer if domain_name.to_text() == 'example.com.' else
            (_ for _ in ()).throw(dns.resolver.NoAnswer)
        ))
        caa_request = CaaCheckRequest(domain_or_ip_target='example.com',
                                      caa_check_parameters=CaaCheckParameters(certificate_type=CertificateType.TLS_SERVER,
                                                                              caa_domains=['ca111.com']))

        caa_checker = MpicCaaChecker()
        result = caa_checker.check_caa(caa_request)
        assert result['statusCode'] == 200
        check_response_details = CaaCheckResponseDetails(present=True, found_at='example.com', response=test_dns_query_answer.rrset.to_text())
        assert self.is_result_as_expected(result, True, check_response_details) is True

    def check_caa_should_return_200_and_disallow_issuance_given_non_matching_caa_record_found(self, set_env_variables, mocker):
        test_dns_query_answer = TestMpicCaaChecker.create_dns_query_answer('example.com', 'ca222.org', 'issue', mocker)
        mocker.patch('dns.resolver.resolve', side_effect=lambda domain_name, rdtype: (
            test_dns_query_answer if domain_name.to_text() == 'example.com.' else
            (_ for _ in ()).throw(dns.resolver.NoAnswer)
        ))
        caa_request = CaaCheckRequest(domain_or_ip_target='example.com',
                                      caa_check_parameters=CaaCheckParameters(certificate_type=CertificateType.TLS_SERVER,
                                                                              caa_domains=['ca111.com']))

        caa_checker = MpicCaaChecker()
        result = caa_checker.check_caa(caa_request)
        assert result['statusCode'] == 200
        check_response_details = CaaCheckResponseDetails(present=True, found_at='example.com',
                                                         response=test_dns_query_answer.rrset.to_text())
        assert self.is_result_as_expected(result, False, check_response_details) is True

    def check_caa_should_return_200_and_allow_issuance_relying_on_default_caa_domains(self, set_env_variables, mocker):
        test_dns_query_answer = TestMpicCaaChecker.create_dns_query_answer('example.com', 'ca2.net', 'issue', mocker)
        mocker.patch('dns.resolver.resolve', side_effect=lambda domain_name, rdtype: (
            test_dns_query_answer if domain_name.to_text() == 'example.com.' else
            (_ for _ in ()).throw(dns.resolver.NoAnswer)
        ))
        caa_request = CaaCheckRequest(domain_or_ip_target='example.com')
        caa_checker = MpicCaaChecker()
        result = caa_checker.check_caa(caa_request)
        assert result['statusCode'] == 200
        check_response_details = CaaCheckResponseDetails(present=True, found_at='example.com', response=test_dns_query_answer.rrset.to_text())
        assert self.is_result_as_expected(result, True, check_response_details) is True

    def check_caa_should_include_timestamp_in_nanos_in_result(self, set_env_variables, mocker):
        mocker.patch('dns.resolver.resolve', side_effect=lambda domain_name, rdtype: exec('raise(dns.resolver.NoAnswer)'))
        caa_request = CaaCheckRequest(domain_or_ip_target='example.com', caa_check_parameters=CaaCheckParameters(
                                          certificate_type=CertificateType.TLS_SERVER, caa_domains=['ca111.com']))
        caa_checker = MpicCaaChecker()
        result = caa_checker.check_caa(caa_request)
        assert result['statusCode'] == 200
        result_body = json.loads(result['body'])
        response_object = CaaCheckResponse.model_validate(result_body)
        assert response_object.timestamp_ns is not None

    def find_caa_record_and_domain__should_return_rrset_and_domain_given_domain_with_caa_record(self, set_env_variables, mocker):
        # mock dns.resolver.resolve to return a valid response
        test_dns_query_answer = TestMpicCaaChecker.create_dns_query_answer('example.com', 'ca1.org', 'issue', mocker)
        mocker.patch('dns.resolver.resolve', side_effect=lambda domain_name, rdtype: (
            test_dns_query_answer if domain_name.to_text() == 'example.com.' else self.raise_(dns.resolver.NoAnswer)
        ))
        caa_request = CaaCheckRequest(domain_or_ip_target='example.com', certificate_type=None, caa_domains=None)
        caa_checker = MpicCaaChecker()
        answer_rrset, domain = caa_checker.find_caa_record_and_domain(caa_request)
        assert isinstance(answer_rrset, RRset)
        assert isinstance(domain, dns.name.Name) and domain.to_text() == 'example.com.'

    def find_caa_record_and_domain__should_return_rrset_and_domain_given_extra_subdomain(self, set_env_variables, mocker):
        test_dns_query_answer = TestMpicCaaChecker.create_dns_query_answer('example.com', 'ca1.org', 'issue', mocker)
        mocker.patch('dns.resolver.resolve', side_effect=lambda domain_name, rdtype: (
            test_dns_query_answer if domain_name.to_text() == 'example.com.' else self.raise_(dns.resolver.NoAnswer)
        ))
        caa_request = CaaCheckRequest(domain_or_ip_target='www.example.com', certificate_type=None, caa_domains=None)
        caa_checker = MpicCaaChecker()
        answer_rrset, domain = caa_checker.find_caa_record_and_domain(caa_request)
        assert isinstance(answer_rrset, RRset)
        assert isinstance(domain, dns.name.Name) and domain.to_text() == 'example.com.'

    def find_caa_record_and_domain__should_return_none_and_root_domain_given_no_caa_record_for_domain(self, set_env_variables, mocker):
        test_dns_query_answer = TestMpicCaaChecker.create_dns_query_answer('example.com', 'ca1.org', 'issue', mocker)
        mocker.patch('dns.resolver.resolve', side_effect=lambda domain_name, rdtype: (
            test_dns_query_answer if domain_name.to_text() == 'example.org.' else self.raise_(dns.resolver.NoAnswer)
        ))
        caa_request = CaaCheckRequest(domain_or_ip_target='example.com', certificate_type=None, caa_domains=None)
        caa_checker = MpicCaaChecker()
        answer_rrset, domain = caa_checker.find_caa_record_and_domain(caa_request)
        assert answer_rrset is None
        assert isinstance(domain, dns.name.Name) and domain.to_text() == '.'  # try everything up to root domain

    @pytest.mark.parametrize('value_list, caa_domains', [
        (['ca111.org'], ['ca111.org']),
        (['ca111.org', 'ca222.com'], ['ca222.com']),
        (['ca111.org', 'ca222.com'], ['ca333.net', 'ca111.org']),
    ])
    def does_value_list_permit_issuance__should_return_true_given_one_value_found_in_caa_domains(self, value_list, caa_domains):
        result = MpicCaaChecker.does_value_list_permit_issuance(value_list, caa_domains)
        assert result is True

    def does_value_list_permit_issuance__should_return_false_given_value_not_found_in_caa_domains(self):
        value_list = ['ca222.org']
        caa_domains = ['ca111.com']
        result = MpicCaaChecker.does_value_list_permit_issuance(value_list, caa_domains)
        assert result is False

    def does_value_list_permit_issuance__should_return_false_given_only_values_with_extensions(self):
        value_list = ['0 issue "ca111.com; policy=ev"']
        caa_domains = ['ca111.com']
        result = MpicCaaChecker.does_value_list_permit_issuance(value_list, caa_domains)
        assert result is False

    def does_value_list_permit_issuance__should_ignore_whitespace_around_values(self):
        value_list = ['  ca111.com  ']
        caa_domains = ['ca111.com']
        result = MpicCaaChecker.does_value_list_permit_issuance(value_list, caa_domains)
        assert result is True

    def is_valid_for_issuance__should_return_true_given_rrset_contains_domain(self, test_rrset):
        caa_domains = ['ca111.com']
        is_wc_domain = False
        test_rrset.add(CAA(CAA_RDCLASS, CAA_RDTYPE, flags=0, tag=b'issue', value=caa_domains[0].encode('utf-8')))
        result = MpicCaaChecker.is_valid_for_issuance(caa_domains, is_wc_domain, test_rrset)
        assert result is True

    def is_valid_for_issuance__should_return_true_given_rrset_contains_domain_and_domain_is_wildcard(self, test_rrset):
        caa_domains = ['ca111.org']
        is_wc_domain = True
        test_rrset.add(CAA(CAA_RDCLASS, CAA_RDTYPE, flags=0, tag=b'issue', value=caa_domains[0].encode('utf-8')))
        result = MpicCaaChecker.is_valid_for_issuance(caa_domains, is_wc_domain, test_rrset)
        assert result is True

    def is_valid_for_issuance__should_return_true_given_rrset_contains_domain_with_issuewild_tag_and_domain_is_wildcard(self, test_rrset):
        caa_domains = ['ca111.com']
        caa_rdata = CAA(CAA_RDCLASS, CAA_RDTYPE, flags=0, tag=b'issuewild', value=caa_domains[0].encode('utf-8'))
        test_rrset.add(caa_rdata)
        is_wc_domain = True
        result = MpicCaaChecker.is_valid_for_issuance(caa_domains, is_wc_domain, test_rrset)
        assert result is True

    def is_valid_for_issuance__should_return_true_given_rrset_contains_no_issue_tags(self, test_rrset):
        caa_domains = ['ca111.com']
        caa_rdata = CAA(CAA_RDCLASS, CAA_RDTYPE, flags=0, tag=b'unknown', value=caa_domains[0].encode('utf-8'))
        test_rrset = RRset(name=dns.name.from_text('example.com'), rdclass=CAA_RDCLASS, rdtype=CAA_RDTYPE)
        test_rrset.add(caa_rdata)
        is_wc_domain = False
        result = MpicCaaChecker.is_valid_for_issuance(caa_domains, is_wc_domain, test_rrset)
        assert result is True

    def is_valid_for_issuance_should_return_false_given_rrset_contains_domain_with_issuewild_tag_and_domain_is_not_wildcard(self, test_rrset):
        caa_domains = ['ca111.com']
        caa_rdata = CAA(CAA_RDCLASS, CAA_RDTYPE, flags=0, tag=b'issuewild', value=caa_domains[0].encode('utf-8'))
        test_rrset.add(caa_rdata)
        is_wc_domain = False
        result = MpicCaaChecker.is_valid_for_issuance(caa_domains, is_wc_domain, test_rrset)
        assert result is False

    @pytest.mark.parametrize('caa_domain, rr_domain', [('ca222.org', 'ca222.org'), ('ca222.org', 'ca111.com')])
    def is_valid_for_issuance__should_return_false_given_rrset_contains_unknown_tag_with_critical_flags(self, test_rrset, caa_domain, rr_domain):
        caa_domains = [caa_domain]
        caa_rdata = CAA(CAA_RDCLASS, CAA_RDTYPE, flags=128, tag=b'mystery', value=rr_domain.encode('utf-8'))
        test_rrset.add(caa_rdata)
        is_wc_domain = False
        result = MpicCaaChecker.is_valid_for_issuance(caa_domains, is_wc_domain, test_rrset)
        assert result is False

    def raise_(self, ex):
        # noinspection PyUnusedLocal
        def _raise(*args, **kwargs):
            raise ex
        return _raise()

    def is_result_as_expected(self, result, check_passed, check_response_details):
        result_body = json.loads(result['body'])
        response_object = CaaCheckResponse.model_validate(result_body)
        response_object.timestamp_ns = None  # ignore timestamp for comparison
        expected_response = CaaCheckResponse(perspective='us-east-4', check_passed=check_passed, details=check_response_details)
        return json.dumps(response_object.model_dump()) == json.dumps(expected_response.model_dump())


if __name__ == '__main__':
    pytest.main()
