import json

import dns
import pytest
from aws_lambda_python.common_domain.check_parameters import DcvCheckParameters, DcvValidationDetails
from aws_lambda_python.common_domain.check_request import DcvCheckRequest
from aws_lambda_python.common_domain.check_response import DcvCheckResponse, DcvCheckResponseDetails, AnnotatedCheckResponse
from aws_lambda_python.common_domain.enum.certificate_type import CertificateType
from aws_lambda_python.common_domain.enum.dcv_validation_method import DcvValidationMethod
from aws_lambda_python.mpic_dcv_checker.mpic_dcv_checker import MpicDcvChecker
from dns.flags import Flag
from dns.rdtypes.ANY.CAA import CAA
from dns.rrset import RRset

CAA_RDCLASS = dns.rdataclass.IN
CAA_RDTYPE = dns.rdatatype.CAA


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
        test_dns_query_answer = TestMpicDcvChecker.create_dns_query_answer('example.com', 'ca111.com', 'issue', mocker)
        mocker.patch('dns.resolver.resolve', side_effect=lambda domain_name, rdtype: (
            test_dns_query_answer if domain_name.to_text() == 'example.com.' else
            (_ for _ in ()).throw(dns.resolver.NoAnswer)
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

    @pytest.mark.skip(reason='not implemented')
    def perform_http_validation__should_return_check_passed_true_given_request_token_file_found(self, set_env_variables, mocker):
        # mock dns.resolver.resolve to return a valid response
        test_dns_query_answer = TestMpicDcvChecker.create_dns_query_answer('example.com', 'ca1.org', 'issue', mocker)
        mocker.patch('requests.get', side_effect=lambda url: (
            type('Response', (object,), {'status_code': 200, 'text': 'challenge'})() if url == 'http://example.com/challenge' else
            type('Response', (object,), {'status_code': 404, 'reason': 'Not Found'})()
        ))
        dcv_request = DcvCheckRequest(domain_or_ip_target='example.com', certificate_type=None, caa_domains=None)
        dcv_checker = MpicDcvChecker()
        answer_rrset, domain = dcv_checker.perform_http_validation(dcv_request)
        assert isinstance(answer_rrset, RRset)
        assert isinstance(domain, dns.name.Name) and domain.to_text() == 'example.com.'


if __name__ == '__main__':
    pytest.main()
