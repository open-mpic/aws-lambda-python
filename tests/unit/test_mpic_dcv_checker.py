import json

import dns
import pytest
from aws_lambda_python.common_domain.check_parameters import DcvCheckParameters, DcvValidationDetails
from aws_lambda_python.common_domain.check_request import DcvCheckRequest
from aws_lambda_python.common_domain.check_response import DcvCheckResponse, DcvCheckResponseDetails
from aws_lambda_python.common_domain.enum.certificate_type import CertificateType
from aws_lambda_python.common_domain.enum.dcv_validation_method import DcvValidationMethod
from aws_lambda_python.common_domain.enum.dns_record_type import DnsRecordType
from aws_lambda_python.mpic_dcv_checker.mpic_dcv_checker import MpicDcvChecker
from dns.flags import Flag
from dns.rdtypes.ANY.CNAME import CNAME
from dns.rdtypes.ANY.TXT import TXT
from dns.rrset import RRset


# noinspection PyMethodMayBeStatic
class TestMpicDcvChecker:
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
    def create_cname_rrset(self):
        dns_record_1 = CNAME(dns.rdataclass.IN, dns.rdatatype.CNAME, target_name=dns.name.from_text('111.ca1.com'))
        dns_record_2 = CNAME(dns.rdataclass.IN, dns.rdatatype.CNAME, target_name=dns.name.from_text('222.ca2.org'))
        rrset = RRset(name=dns.name.from_text('_dnsauth.example.com'), rdclass=dns.rdataclass.IN, rdtype=dns.rdatatype.CNAME)
        rrset.add(dns_record_1)
        rrset.add(dns_record_2)
        return rrset

    @staticmethod
    def create_dns_query_answer(domain, dcv_validation_details: DcvValidationDetails, mocker):
        challenge_value = dcv_validation_details.challenge_value
        dns_name_prefix = dcv_validation_details.dns_name_prefix
        record_type = dcv_validation_details.dns_record_type
        dns_record_1 = None
        if record_type == DnsRecordType.CNAME:
            dns_record_1 = CNAME(dns.rdataclass.IN, dns.rdatatype.CNAME, target=challenge_value)
        elif record_type == DnsRecordType.TXT:
            dns_record_1 = TXT(dns.rdataclass.IN, dns.rdatatype.TXT, strings=[challenge_value.encode('utf-8')])
        good_response = dns.message.QueryMessage()
        good_response.flags = Flag.QR
        rrset_domain = f"{dns_name_prefix}.{domain}"
        response_question_rrset = RRset(name=dns.name.from_text(rrset_domain), rdclass=dns.rdataclass.IN, rdtype=dns.rdatatype.from_text(record_type))
        good_response.question = [response_question_rrset]
        response_answer_rrset = RRset(name=dns.name.from_text(rrset_domain), rdclass=dns.rdataclass.IN, rdtype=dns.rdatatype.from_text(record_type))
        response_answer_rrset.add(dns_record_1)
        good_response.answer = [response_answer_rrset]  # caa checker doesn't look here, but dcv checker does
        mocker.patch('dns.message.Message.find_rrset', return_value=response_answer_rrset)  # needed for Answer constructor to work
        return dns.resolver.Answer(qname=dns.name.from_text(rrset_domain), rdtype=dns.rdatatype.from_text(record_type), rdclass=dns.rdataclass.IN, response=good_response)

    @staticmethod
    def create_http_check_request():
        return DcvCheckRequest(domain_or_ip_target='example.com',
                               dcv_check_parameters=DcvCheckParameters(
                                   validation_method=DcvValidationMethod.HTTP_GENERIC,
                                   validation_details=DcvValidationDetails(
                                       http_token_path='/.well-known/pki_validation/token111_ca1.txt',
                                       challenge_value='challenge_111')
                               ))

    @staticmethod
    def create_dns_check_request(record_type=DnsRecordType.TXT):
        return DcvCheckRequest(domain_or_ip_target='example.com',
                               dcv_check_parameters=DcvCheckParameters(
                                   validation_method=DcvValidationMethod.DNS_GENERIC,
                                   validation_details=DcvValidationDetails(
                                       dns_name_prefix='_dnsauth',
                                       dns_record_type=record_type,
                                       challenge_value=f"{record_type}_challenge_111.ca1.com.")
                               ))

    @pytest.mark.skip(reason='not implemented')
    # integration test of a sort -- only mocking dns methods rather than remaining class methods
    def check_dcv__should_return_200_and_allow_issuance_given_target_record_found(self, set_env_variables, mocker):
        mocker.patch('dns.resolver.resolve', side_effect=lambda domain_name, rdtype: exec('raise(dns.resolver.NoAnswer)'))
        dcv_request = DcvCheckRequest(domain_or_ip_target='example.com',
                                      dcv_check_parameters=DcvCheckParameters(
                                            validation_method=DcvValidationMethod.HTTP_GENERIC,
                                            validation_details=DcvValidationDetails(path='challenge', expected_challenge='challenge')
                                      ))
        dcv_checker = MpicDcvChecker()
        result = dcv_checker.check_dcv(dcv_request)
        assert result['statusCode'] == 200
        result_body = json.loads(result['body'])
        response_object = DcvCheckResponse.model_validate(result_body)
        response_object.timestamp_ns = None  # ignore timestamp for comparison
        expected_response = DcvCheckResponse(perspective='us-east-4', check_passed=True, details=DcvCheckResponseDetails(present=False))
        assert json.dumps(response_object.model_dump()) == json.dumps(expected_response.model_dump())

    @pytest.mark.skip(reason='not implemented')
    def check_caa__should_return_200_and_allow_issuance_given_matching_caa_record_found(self, set_env_variables, mocker):
        test_dns_query_answer = TestMpicDcvChecker.create_dns_query_answer('example.com', 'ca111.com', DnsRecordType.CNAME, 'issue', mocker)
        mocker.patch('dns.resolver.resolve', side_effect=lambda domain_name, rdtype: (
            test_dns_query_answer if domain_name.to_text() == 'example.com.' else self.raise_(dns.resolver.NoAnswer)
        ))
        dcv_request = DcvCheckRequest(domain_or_ip_target='example.com',
                                      caa_check_parameters=DcvCheckParameters(certificate_type=CertificateType.TLS_SERVER,
                                                                              caa_domains=['ca111.com']))

        dcv_checker = MpicDcvChecker()
        result = dcv_checker.check_dcv(dcv_request)
        assert result['statusCode'] == 200
        result_body = json.loads(result['body'])
        response_object = DcvCheckResponse.model_validate(result_body)
        response_object.timestamp_ns = None  # ignore timestamp for comparison
        expected_response = DcvCheckResponse(perspective='us-east-4', check_passed=True,
                                             details=DcvCheckResponseDetails(present=True, found_at='example.com',
                                                                             response=test_dns_query_answer.rrset.to_text()))
        assert json.dumps(response_object.model_dump()) == json.dumps(expected_response.model_dump())

    @pytest.mark.skip(reason='not implemented')
    def check_caa_should_include_timestamp_in_nanos_in_result(self, set_env_variables, mocker):
        mocker.patch('dns.resolver.resolve', side_effect=lambda domain_name, rdtype: exec('raise(dns.resolver.NoAnswer)'))
        dcv_request = DcvCheckRequest(domain_or_ip_target='example.com', caa_check_parameters=DcvCheckParameters(
                                          certificate_type=CertificateType.TLS_SERVER, caa_domains=['ca111.com']))
        dcv_checker = MpicDcvChecker()
        result = dcv_checker.check_dcv(dcv_request)
        assert result['statusCode'] == 200
        result_body = json.loads(result['body'])
        response_object = DcvCheckResponse.model_validate(result_body)
        assert response_object.timestamp_ns is not None

    def perform_http_validation__should_return_check_passed_true_with_details_given_request_token_file_found(self, set_env_variables, mocker):
        dcv_request = TestMpicDcvChecker.create_http_check_request()
        expected_url = f"http://{dcv_request.domain_or_ip_target}/{dcv_request.dcv_check_parameters.validation_details.http_token_path}"  # noqa E501 (http)
        expected_challenge = dcv_request.dcv_check_parameters.validation_details.challenge_value
        mocker.patch('requests.get', side_effect=lambda url: (
            type('Response', (object,), {'status_code': 200, 'text': expected_challenge})() if url == expected_url else
            type('Response', (object,), {'status_code': 404, 'reason': 'Not Found'})()
        ))
        dcv_checker = MpicDcvChecker()
        response = dcv_checker.perform_http_validation(dcv_request)
        assert response['statusCode'] == 200
        dcv_check_response = DcvCheckResponse.model_validate(json.loads(response['body']))
        assert dcv_check_response.check_passed is True
        assert dcv_check_response.perspective == 'us-east-4'

    def perform_http_validation__should_return_check_passed_false_with_details_given_request_token_file_not_found(self, set_env_variables, mocker):
        dcv_request = TestMpicDcvChecker.create_http_check_request()
        mocker.patch('requests.get', return_value=type('Response', (object,), {'status_code': 404, 'reason': 'Not Found'})())
        dcv_checker = MpicDcvChecker()
        response = dcv_checker.perform_http_validation(dcv_request)
        assert response['statusCode'] == 404
        dcv_check_response = DcvCheckResponse.model_validate(json.loads(response['body']))
        assert dcv_check_response.check_passed is False
        assert dcv_check_response.errors[0].error_type == '404'
        assert dcv_check_response.errors[0].error_message == 'Not Found'

    @pytest.mark.parametrize('record_type', [DnsRecordType.TXT, DnsRecordType.CNAME])
    def perform_dns_validation__should_return_check_passed_true_with_details_given_expected_dns_record_found(self, set_env_variables, record_type, mocker):
        dcv_request = TestMpicDcvChecker.create_dns_check_request(record_type)
        dcv_details = dcv_request.dcv_check_parameters.validation_details
        expected_domain = f"{dcv_details.dns_name_prefix}.{dcv_request.domain_or_ip_target}"
        test_dns_query_answer = TestMpicDcvChecker.create_dns_query_answer(dcv_request.domain_or_ip_target, dcv_details, mocker)
        mocker.patch('dns.resolver.resolve', side_effect=lambda domain_name, rdtype: (
            test_dns_query_answer if domain_name == expected_domain else self.raise_(dns.resolver.NoAnswer)
        ))
        dcv_checker = MpicDcvChecker()
        response = dcv_checker.perform_dns_validation(dcv_request)
        assert response['statusCode'] == 200
        dcv_check_response = DcvCheckResponse.model_validate(json.loads(response['body']))
        assert dcv_check_response.check_passed is True
        assert dcv_check_response.perspective == 'us-east-4'

    def perform_dns_validation__should_return_check_passed_false_with_details_given_expected_dns_record_not_found(self, set_env_variables, mocker):
        dcv_request = TestMpicDcvChecker.create_dns_check_request()
        mocker.patch('dns.resolver.resolve', side_effect=lambda domain_name, rdtype: self.raise_(dns.resolver.NoAnswer))
        dcv_checker = MpicDcvChecker()
        response = dcv_checker.perform_dns_validation(dcv_request)
        assert response['statusCode'] == 500
        dcv_check_response = DcvCheckResponse.model_validate(json.loads(response['body']))
        assert dcv_check_response.check_passed is False
        assert dcv_check_response.errors[0].error_type == dns.resolver.NoAnswer.__name__
        assert 'answer' in dcv_check_response.errors[0].error_message

    def raise_(self, ex):
        # noinspection PyUnusedLocal
        def _raise(*args, **kwargs):
            raise ex
        return _raise()


if __name__ == '__main__':
    pytest.main()
