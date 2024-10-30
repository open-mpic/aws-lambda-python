import json

import dns
import pytest
from aws_lambda_python.common_domain.check_parameters import CaaCheckParameters
from aws_lambda_python.common_domain.check_request import CaaCheckRequest
from aws_lambda_python.common_domain.check_response import CaaCheckResponse, CaaCheckResponseDetails
from aws_lambda_python.common_domain.enum.certificate_type import CertificateType
from aws_lambda_python.common_domain.remote_perspective import RemotePerspective
from aws_lambda_python.common_domain.validation_error import ValidationError
from aws_lambda_python.common_domain.messages.ErrorMessages import ErrorMessages
from aws_lambda_python.mpic_caa_checker.mpic_caa_checker import MpicCaaChecker
from dns.rrset import RRset

from mock_dns_object_creator import MockDnsObjectCreator


# noinspection PyMethodMayBeStatic
class TestMpicCaaChecker:
    @staticmethod
    @pytest.fixture(scope='class')
    def set_env_variables():
        envvars = {
            'default_caa_domains': 'ca1.com|ca2.net|ca3.org',
            'AWS_REGION': 'us-east-4',
            'rir_region': 'arin',
        }
        with pytest.MonkeyPatch.context() as class_scoped_monkeypatch:
            for k, v in envvars.items():
                class_scoped_monkeypatch.setenv(k, v)
            yield class_scoped_monkeypatch  # restore the environment afterward

    @staticmethod
    def create_configured_caa_checker():
        return MpicCaaChecker(["ca1.com", "ca2.net", "ca3.org"], RemotePerspective.from_rir_code("arin.us-east-4"))

    # integration test of a sort -- only mocking dns methods rather than remaining class methods
    def check_caa__should_return_200_and_allow_issuance_given_no_caa_records_found(self, set_env_variables, mocker):
        mocker.patch('dns.resolver.resolve', side_effect=lambda domain_name, rdtype: exec('raise(dns.resolver.NoAnswer)'))
        caa_request = CaaCheckRequest(domain_or_ip_target='example.com',
                                      caa_check_parameters=CaaCheckParameters(certificate_type=CertificateType.TLS_SERVER, caa_domains=['ca111.com']))
        caa_checker = TestMpicCaaChecker.create_configured_caa_checker()
        result = caa_checker.check_caa(caa_request)
        assert result['statusCode'] == 200
        check_response_details = CaaCheckResponseDetails(caa_record_present=False)
        assert self.is_result_as_expected(result, True, check_response_details) is True

    def check_caa__should_return_200_and_allow_issuance_given_matching_caa_record_found(self, set_env_variables, mocker):
        test_dns_query_answer = MockDnsObjectCreator.create_caa_query_answer('example.com', 0, 'issue', 'ca111.com', mocker)
        mocker.patch('dns.resolver.resolve', side_effect=lambda domain_name, rdtype: (
            test_dns_query_answer if domain_name.to_text() == 'example.com.' else
            (_ for _ in ()).throw(dns.resolver.NoAnswer)
        ))
        caa_request = CaaCheckRequest(domain_or_ip_target='example.com',
                                      caa_check_parameters=CaaCheckParameters(certificate_type=CertificateType.TLS_SERVER,
                                                                              caa_domains=['ca111.com']))

        caa_checker = TestMpicCaaChecker.create_configured_caa_checker()
        result = caa_checker.check_caa(caa_request)
        assert result['statusCode'] == 200
        check_response_details = CaaCheckResponseDetails(caa_record_present=True, found_at='example.com', response=test_dns_query_answer.rrset.to_text())
        assert self.is_result_as_expected(result, True, check_response_details) is True

    def check_caa__should_return_200_and_allow_issuance_given_matching_caa_record_found_in_parent_of_nonexistent_domain(self, set_env_variables, mocker):
        test_dns_query_answer = MockDnsObjectCreator.create_caa_query_answer('example.com', 0, 'issue', 'ca111.com', mocker)
        mocker.patch('dns.resolver.resolve', side_effect=lambda domain_name, rdtype: (
            test_dns_query_answer if domain_name.to_text() == 'example.com.' else
            (_ for _ in ()).throw(dns.resolver.NXDOMAIN)
        ))
        caa_request = CaaCheckRequest(domain_or_ip_target='notexisting.example.com',
                                      caa_check_parameters=CaaCheckParameters(certificate_type=CertificateType.TLS_SERVER,
                                                                              caa_domains=['ca111.com']))

        caa_checker = TestMpicCaaChecker.create_configured_caa_checker()
        result = caa_checker.check_caa(caa_request)
        assert result['statusCode'] == 200
        check_response_details = CaaCheckResponseDetails(caa_record_present=True, found_at='example.com', response=test_dns_query_answer.rrset.to_text())
        assert self.is_result_as_expected(result, True, check_response_details) is True
        
    def check_caa__should_return_200_and_disallow_issuance_given_non_matching_caa_record_found(self, set_env_variables, mocker):
        test_dns_query_answer = MockDnsObjectCreator.create_caa_query_answer('example.com', 0, 'issue', 'ca222.com', mocker)
        mocker.patch('dns.resolver.resolve', side_effect=lambda domain_name, rdtype: (
            test_dns_query_answer if domain_name.to_text() == 'example.com.' else
            (_ for _ in ()).throw(dns.resolver.NoAnswer)
        ))
        caa_request = CaaCheckRequest(domain_or_ip_target='example.com',
                                      caa_check_parameters=CaaCheckParameters(certificate_type=CertificateType.TLS_SERVER,
                                                                              caa_domains=['ca111.com']))

        caa_checker = TestMpicCaaChecker.create_configured_caa_checker()
        result = caa_checker.check_caa(caa_request)
        assert result['statusCode'] == 200
        check_response_details = CaaCheckResponseDetails(caa_record_present=True, found_at='example.com',
                                                         response=test_dns_query_answer.rrset.to_text())
        assert self.is_result_as_expected(result, False, check_response_details) is True

    def check_caa__should_return_200_and_allow_issuance_relying_on_default_caa_domains(self, set_env_variables, mocker):
        test_dns_query_answer = MockDnsObjectCreator.create_caa_query_answer('example.com', 0, 'issue', 'ca2.net', mocker)
        mocker.patch('dns.resolver.resolve', side_effect=lambda domain_name, rdtype: (
            test_dns_query_answer if domain_name.to_text() == 'example.com.' else
            (_ for _ in ()).throw(dns.resolver.NoAnswer)
        ))
        caa_request = CaaCheckRequest(domain_or_ip_target='example.com')
        caa_checker = TestMpicCaaChecker.create_configured_caa_checker()
        result = caa_checker.check_caa(caa_request)
        assert result['statusCode'] == 200
        check_response_details = CaaCheckResponseDetails(caa_record_present=True, found_at='example.com', response=test_dns_query_answer.rrset.to_text())
        assert self.is_result_as_expected(result, True, check_response_details) is True

    def check_caa__should_include_timestamp_in_nanos_in_result(self, set_env_variables, mocker):
        mocker.patch('dns.resolver.resolve', side_effect=lambda domain_name, rdtype: self.raise_(dns.resolver.NoAnswer))
        caa_request = CaaCheckRequest(domain_or_ip_target='example.com', caa_check_parameters=CaaCheckParameters(
                                          certificate_type=CertificateType.TLS_SERVER, caa_domains=['ca111.com']))
        caa_checker = TestMpicCaaChecker.create_configured_caa_checker()
        result = caa_checker.check_caa(caa_request)
        assert result['statusCode'] == 200
        result_body = json.loads(result['body'])
        response_object = CaaCheckResponse.model_validate(result_body)
        assert response_object.timestamp_ns is not None

    def check_caa__should_return_failure_response_given_error_in_dns_lookup(self, set_env_variables, mocker):
        mocker.patch('dns.resolver.resolve', side_effect=lambda domain_name, rdtype: self.raise_(dns.resolver.NoNameservers))
        caa_request = CaaCheckRequest(domain_or_ip_target='example.com', caa_check_parameters=CaaCheckParameters(
                                          certificate_type=CertificateType.TLS_SERVER, caa_domains=['ca111.com']))
        caa_checker = TestMpicCaaChecker.create_configured_caa_checker()
        result = caa_checker.check_caa(caa_request)
        assert result['statusCode'] == 200
        check_response_details = CaaCheckResponseDetails(caa_record_present=False)
        errors = [ValidationError(error_type=ErrorMessages.CAA_LOOKUP_ERROR.key, error_message=ErrorMessages.CAA_LOOKUP_ERROR.message)]
        assert self.is_result_as_expected(result, False, check_response_details, errors) is True

    def find_caa_record_and_domain__should_return_rrset_and_domain_given_domain_with_caa_record(self, set_env_variables, mocker):
        # mock dns.resolver.resolve to return a valid response
        test_dns_query_answer = MockDnsObjectCreator.create_caa_query_answer('example.com', 0, 'issue', 'ca1.org', mocker)
        mocker.patch('dns.resolver.resolve', side_effect=lambda domain_name, rdtype: (
            test_dns_query_answer if domain_name.to_text() == 'example.com.' else self.raise_(dns.resolver.NoAnswer)
        ))
        caa_request = CaaCheckRequest(domain_or_ip_target='example.com', certificate_type=None, caa_domains=None)
        caa_checker = TestMpicCaaChecker.create_configured_caa_checker()
        answer_rrset, domain = caa_checker.find_caa_record_and_domain(caa_request)
        assert isinstance(answer_rrset, RRset)
        assert isinstance(domain, dns.name.Name) and domain.to_text() == 'example.com.'

    def find_caa_record_and_domain__should_return_rrset_and_domain_given_extra_subdomain(self, set_env_variables, mocker):
        test_dns_query_answer = MockDnsObjectCreator.create_caa_query_answer('example.com', 0, 'issue', 'ca1.org', mocker)
        mocker.patch('dns.resolver.resolve', side_effect=lambda domain_name, rdtype: (
            test_dns_query_answer if domain_name.to_text() == 'example.com.' else self.raise_(dns.resolver.NoAnswer)
        ))
        caa_request = CaaCheckRequest(domain_or_ip_target='www.example.com', certificate_type=None, caa_domains=None)
        caa_checker = TestMpicCaaChecker.create_configured_caa_checker()
        answer_rrset, domain = caa_checker.find_caa_record_and_domain(caa_request)
        assert isinstance(answer_rrset, RRset)
        assert isinstance(domain, dns.name.Name) and domain.to_text() == 'example.com.'

    def find_caa_record_and_domain__should_return_none_and_root_domain_given_no_caa_record_for_domain(self, set_env_variables, mocker):
        test_dns_query_answer = MockDnsObjectCreator.create_caa_query_answer('example.com', 0, 'issue', 'ca1.org', mocker)
        mocker.patch('dns.resolver.resolve', side_effect=lambda domain_name, rdtype: (
            test_dns_query_answer if domain_name.to_text() == 'example.org.' else self.raise_(dns.resolver.NoAnswer)
        ))
        caa_request = CaaCheckRequest(domain_or_ip_target='example.com', certificate_type=None, caa_domains=None)
        caa_checker = TestMpicCaaChecker.create_configured_caa_checker()
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

    def is_valid_for_issuance__should_return_true_given_issue_tag_for_non_wildcard_domain(self):
        test_rrset = MockDnsObjectCreator.create_caa_rrset(MockDnsObjectCreator.create_caa_record(0, 'issue', 'ca1.org'))
        result = MpicCaaChecker.is_valid_for_issuance(caa_domains=['ca1.org'], is_wc_domain=False, rrset=test_rrset)
        assert result is True

    def is_valid_for_issuance__should_return_true_given_issue_tag_for_wildcard_domain(self):
        test_rrset = MockDnsObjectCreator.create_caa_rrset(MockDnsObjectCreator.create_caa_record(0, 'issue', 'ca1.org'))
        result = MpicCaaChecker.is_valid_for_issuance(caa_domains=['ca1.org'], is_wc_domain=True, rrset=test_rrset)
        assert result is True

    def is_valid_for_issuance__should_return_true_given_issuewild_tag_for_wildcard_domain(self):
        test_rrset = MockDnsObjectCreator.create_caa_rrset(MockDnsObjectCreator.create_caa_record(0, 'issuewild', 'ca1.org'),
                                                           MockDnsObjectCreator.create_caa_record(0, 'issue', 'ca2.org'))
        result = MpicCaaChecker.is_valid_for_issuance(caa_domains=['ca1.org'], is_wc_domain=True, rrset=test_rrset)
        assert result is True

    def is_valid_for_issuance__should_return_true_given_no_issue_tags_and_issuewild_tag_for_wildcard_domain(self):
        test_rrset = MockDnsObjectCreator.create_caa_rrset(MockDnsObjectCreator.create_caa_record(0, 'issuewild', 'ca1.org'))
        result = MpicCaaChecker.is_valid_for_issuance(caa_domains=['ca1.org'], is_wc_domain=True, rrset=test_rrset)
        assert result is True

    def is_valid_for_issuance__should_return_true_given_issuewild_disallowed_for_all_and_issue_tag_found(self):
        test_rrset = MockDnsObjectCreator.create_caa_rrset(MockDnsObjectCreator.create_caa_record(0, 'issue', 'ca1.org'),
                                                           MockDnsObjectCreator.create_caa_record(0, 'issuewild', ';'))
        result = MpicCaaChecker.is_valid_for_issuance(caa_domains=['ca1.org'], is_wc_domain=False, rrset=test_rrset)
        assert result is True

    def is_valid_for_issuance__should_return_true_given_no_issue_tags_found(self):
        test_rrset = MockDnsObjectCreator.create_caa_rrset(MockDnsObjectCreator.create_caa_record(0, 'unknown', 'ca1.org'))
        result = MpicCaaChecker.is_valid_for_issuance(caa_domains=['ca1.org'], is_wc_domain=False, rrset=test_rrset)
        assert result is True

    def is_valid_for_issuance__should_return_false_given_issue_tags_for_other_certificate_authorities_only(self):
        test_rrset = MockDnsObjectCreator.create_caa_rrset(MockDnsObjectCreator.create_caa_record(0, 'issue', 'ca5.org'))
        result = MpicCaaChecker.is_valid_for_issuance(caa_domains=['ca1.org'], is_wc_domain=False, rrset=test_rrset)
        assert result is False

    @pytest.mark.parametrize('known_tag', ['issue'])  # TODO what about issuewild, issuemail, and iodef? (they fail)
    def is_valid_for_issuance__should_return_true_given_critical_flag_and_known_tag(self, known_tag):
        test_rrset = MockDnsObjectCreator.create_caa_rrset(MockDnsObjectCreator.create_caa_record(128, known_tag, 'ca1.org'))
        result = MpicCaaChecker.is_valid_for_issuance(caa_domains=['ca1.org'], is_wc_domain=False, rrset=test_rrset)
        assert result is True

    def is_valid_for_issuance__should_return_false_given_critical_flag_for_an_unknown_tag(self):
        test_rrset = MockDnsObjectCreator.create_caa_rrset(MockDnsObjectCreator.create_caa_record(128, 'mystery', 'ca1.org'),
                                                           MockDnsObjectCreator.create_caa_record(0, 'issue', 'ca1.org'))
        result = MpicCaaChecker.is_valid_for_issuance(caa_domains=['ca1.org'], is_wc_domain=False, rrset=test_rrset)
        assert result is False

    def is_valid_for_issuance__should_return_false_given_issuewild_disallowed_for_all_and_wildcard_domain(self):
        test_rrset = MockDnsObjectCreator.create_caa_rrset(MockDnsObjectCreator.create_caa_record(0, 'issue', 'ca1.org'),
                                                           MockDnsObjectCreator.create_caa_record(0, 'issuewild', ';'))
        result = MpicCaaChecker.is_valid_for_issuance(caa_domains=['ca1.org'], is_wc_domain=True, rrset=test_rrset)
        assert result is False

    @pytest.mark.parametrize('issue_tag', ['ISSUE', 'IsSuE'])
    def is_valid_for_issuance__should_return_true_given_nonstandard_casing_in_issue_tag(self, issue_tag):
        test_rrset = MockDnsObjectCreator.create_caa_rrset(MockDnsObjectCreator.create_caa_record(0, issue_tag, 'ca1.org'))
        result = MpicCaaChecker.is_valid_for_issuance(caa_domains=['ca1.org'], is_wc_domain=False, rrset=test_rrset)
        assert result is True

    def is_valid_for_issuance__should_return_false_given_attempted_xss_via_caa_record(self):
        test_rrset = MockDnsObjectCreator.create_caa_rrset(MockDnsObjectCreator.create_caa_record(0, 'issue', 'ca1.org <script>alert("XSS")</script>'))
        result = MpicCaaChecker.is_valid_for_issuance(caa_domains=['ca1.org'], is_wc_domain=False, rrset=test_rrset)
        assert result is False

    @pytest.mark.skip(reason='Checks for DNSSEC validity are not yet implemented')
    def is_valid_for_issuance__should_return_false_given_expired_dnssec_signature(self):
        test_rrset = MockDnsObjectCreator.create_caa_rrset(MockDnsObjectCreator.create_caa_record(0, 'issue', 'ca1.org'))
        result = MpicCaaChecker.is_valid_for_issuance(caa_domains=['ca1.org'], is_wc_domain=False, rrset=test_rrset)
        assert result is False

    @pytest.mark.parametrize('domain_1_tag, domain_1_value, expected_result', [
        ('issue', ';', False), ('issue', 'ca2.org', False), ('mystery', 'ca2.org', True)
    ])
    def is_valid_for_issuance__should_ignore_issuewild_tags_given_non_wildcard_domain(self, domain_1_tag, domain_1_value, expected_result):
        test_rrset = MockDnsObjectCreator.create_caa_rrset(MockDnsObjectCreator.create_caa_record(0, domain_1_tag, domain_1_value),
                                                           MockDnsObjectCreator.create_caa_record(0, 'issuewild', 'ca1.org'))
        result = MpicCaaChecker.is_valid_for_issuance(caa_domains=['ca1.org'], is_wc_domain=False, rrset=test_rrset)
        assert result is expected_result

    def raise_(self, ex):
        # noinspection PyUnusedLocal
        def _raise(*args, **kwargs):
            raise ex
        return _raise()

    def is_result_as_expected(self, result, check_passed, check_response_details, errors=None):
        result_body = json.loads(result['body'])
        response_object = CaaCheckResponse.model_validate(result_body)
        response_object.timestamp_ns = None  # ignore timestamp for comparison
        expected_response = CaaCheckResponse(perspective='arin.us-east-4', check_passed=check_passed, details=check_response_details, errors=errors)
        return response_object == expected_response  # Pydantic allows direct comparison with equality operator


if __name__ == '__main__':
    pytest.main()
