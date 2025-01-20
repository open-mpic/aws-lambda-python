import json
import sys
import pytest
from pydantic import TypeAdapter

from open_mpic_core.common_domain.check_parameters import CaaCheckParameters, DcvWebsiteChangeValidationDetails, DcvAcmeDns01ValidationDetails, DcvDnsChangeValidationDetails
from open_mpic_core.common_domain.check_parameters import DcvCheckParameters
from open_mpic_core.common_domain.enum.certificate_type import CertificateType
from open_mpic_core.common_domain.enum.check_type import CheckType
from open_mpic_core.common_domain.enum.dns_record_type import DnsRecordType
from open_mpic_core.mpic_coordinator.domain.mpic_request import MpicCaaRequest
from open_mpic_core.mpic_coordinator.domain.mpic_request import MpicDcvRequest
from open_mpic_core.mpic_coordinator.domain.mpic_orchestration_parameters import MpicRequestOrchestrationParameters

import testing_api_client
from open_mpic_core.mpic_coordinator.domain.mpic_response import MpicResponse
from open_mpic_core.mpic_coordinator.messages.mpic_request_validation_messages import MpicRequestValidationMessages

MPIC_REQUEST_PATH = "/mpic"


# noinspection PyMethodMayBeStatic
@pytest.mark.integration
class TestDeployedMpicApi:
    @classmethod
    def setup_class(cls):
        cls.mpic_response_adapter = TypeAdapter(MpicResponse)

    @pytest.fixture(scope='class')
    def api_client(self):
        with pytest.MonkeyPatch.context() as class_scoped_monkeypatch:
            # blank out argv except first param; arg parser doesn't expect pytest args
            class_scoped_monkeypatch.setattr(sys, 'argv', sys.argv[:1])
            api_client = testing_api_client.TestingApiClient()
            yield api_client
            api_client.close()

    def api_should_return_200_and_passed_corroboration_given_successful_caa_check(self, api_client):
        request = MpicCaaRequest(
            domain_or_ip_target='example.com',
            orchestration_parameters=MpicRequestOrchestrationParameters(perspective_count=3, quorum_count=2),
            caa_check_parameters=CaaCheckParameters(certificate_type=CertificateType.TLS_SERVER, caa_domains=['mozilla.com'])
        )

        print("\nRequest:\n", json.dumps(request.model_dump(), indent=4))  # pretty print request body
        response = api_client.post(MPIC_REQUEST_PATH, json.dumps(request.model_dump()))
        # response_body_as_json = response.json()
        assert response.status_code == 200
        # assert response body has a list of perspectives with length 2, and each element has response code 200
        mpic_response = self.mpic_response_adapter.validate_json(response.text)
        print("\nResponse:\n", json.dumps(mpic_response.model_dump(), indent=4))  # pretty print response body
        assert mpic_response.is_valid is True
        perspectives_list = mpic_response.perspectives
        assert len(perspectives_list) == request.orchestration_parameters.perspective_count
        assert (len(list(filter(lambda perspective: perspective.check_type == CheckType.CAA, perspectives_list)))
                == request.orchestration_parameters.perspective_count)

    @pytest.mark.parametrize('domain_or_ip_target, purpose_of_test, is_wildcard_domain', [
        ('empty.basic.caatestsuite.com', 'Tests handling of 0 issue ";"', False),
        ('deny.basic.caatestsuite.com', 'Tests handling of 0 issue "caatestsuite.com"', False),
        ('uppercase-deny.basic.caatestsuite.com', 'Tests handling of uppercase issue tag (0 ISSUE "caatestsuite.com")', False),
        ('mixedcase-deny.basic.caatestsuite.com', 'Tests handling of mixed case issue tag (0 IsSuE "caatestsuite.com")', False),
        ('big.basic.caatestsuite.com', 'Tests handling of gigantic (1001) CAA record set (0 issue "caatestsuite.com")', False),
        ('critical1.basic.caatestsuite.com', 'Tests handling of unknown critical property (128 caatestsuitedummyproperty "test")', False),
        ('critical2.basic.caatestsuite.com', 'Tests handling of unknown critical property with another flag (130)', False),
        ('sub1.deny.basic.caatestsuite.com', 'Tests basic tree climbing when CAA record is at parent domain', False),
        ('sub2.sub1.deny.basic.caatestsuite.com', 'Tests tree climbing when CAA record is at grandparent domain', False),
        ('deny.basic.caatestsuite.com', 'Tests handling of issue property for a wildcard domain', True),
        ('deny-wild.basic.caatestsuite.com', 'Tests handling of issuewild for a wildcard domain', True),
        ('cname-deny.basic.caatestsuite.com', 'Tests handling of CNAME, where CAA record is at CNAME target', False),
        ('cname-cname-deny.basic.caatestsuite.com', 'Tests handling of CNAME chain, where CAA record is at ultimate target', False),
        ('sub1.cname-deny.basic.caatestsuite.com', 'Tests handling of CNAME, where parent is CNAME and CAA record is at target', False),
        ('deny.permit.basic.caatestsuite.com', 'Tests rejection when parent name contains a permissible CAA record set', False),
        ('ipv6only.caatestsuite.com', 'Tests handling of record at IPv6-only authoritative name server', False),
        #('expired.caatestsuite-dnssec.com', 'Tests rejection when expired DNSSEC signatures', False), # DNSSEC SHOULD be enabled in production but is not a current requirement for MPIC
        #('missing.caatestsuite-dnssec.com', 'Tests rejection when missing DNSSEC signatures', False), # DNSSEC SHOULD be enabled in production but is not a current requirement for MPIC
        ('blackhole.caatestsuite-dnssec.com', 'Tests rejection when DNSSEC chain goes to non-responsive server', False),
        ('servfail.caatestsuite-dnssec.com', 'Tests rejection when DNSSEC chain goes to server returning SERVFAIL', False),
        ('refused.caatestsuite-dnssec.com', 'Tests rejection when DNSSEC chain goes to server returning REFUSED', False),
        ('xss.caatestsuite.com', 'Tests rejection when issue property has HTML and JS', False),
    ])
    def api_should_return_is_valid_false_for_all_tests_in_do_not_issue_caa_test_suite(self, api_client, domain_or_ip_target,
                                                                                      purpose_of_test, is_wildcard_domain):
        print(f"Running test for {domain_or_ip_target} ({purpose_of_test})")
        if is_wildcard_domain:
            domain_or_ip_target = "*." + domain_or_ip_target
        request = MpicCaaRequest(
            domain_or_ip_target=domain_or_ip_target,
            orchestration_parameters=MpicRequestOrchestrationParameters(perspective_count=3, quorum_count=2),
            caa_check_parameters=CaaCheckParameters(
                certificate_type=CertificateType.TLS_SERVER, caa_domains=['example.com']
            )
        )
        response = api_client.post(MPIC_REQUEST_PATH, json.dumps(request.model_dump()))
        mpic_response = self.mpic_response_adapter.validate_json(response.text)
        assert mpic_response.is_valid is False

    # NOTE: Open MPIC AWS-Lambda-Python currently is not able to communicate with an IPv6 only nameserver.
    # This case is handled in a compliant manner as it is treated as a lookup failure.
    # The test for proper communication with an IPv6 nameserver can be enabled with the following additional parameter to the list below.
    # ('ipv6only.caatestsuite.com', 'Tests handling of record at IPv6-only authoritative name server', False),
    @pytest.mark.parametrize('domain_or_ip_target, purpose_of_test, is_wildcard_domain', [
        ('deny.basic.caatestsuite.com', 'Tests handling of 0 issue "caatestsuite.com"', False),
        ('uppercase-deny.basic.caatestsuite.com', 'Tests handling of uppercase issue tag (0 ISSUE "caatestsuite.com")', False),
        ('mixedcase-deny.basic.caatestsuite.com', 'Tests handling of mixed case issue tag (0 IsSuE "caatestsuite.com")', False),
        ('big.basic.caatestsuite.com', 'Tests handling of gigantic (1001) CAA record set (0 issue "caatestsuite.com")', False),
        ('sub1.deny.basic.caatestsuite.com', 'Tests basic tree climbing when CAA record is at parent domain', False),
        ('sub2.sub1.deny.basic.caatestsuite.com', 'Tests tree climbing when CAA record is at grandparent domain', False),
        ('deny.basic.caatestsuite.com', 'Tests handling of issue property for a wildcard domain', True),
        ('deny-wild.basic.caatestsuite.com', 'Tests handling of issuewild for a wildcard domain', True),
        ('cname-deny.basic.caatestsuite.com', 'Tests handling of CNAME, where CAA record is at CNAME target', False),
        ('cname-cname-deny.basic.caatestsuite.com', 'Tests handling of CNAME chain, where CAA record is at ultimate target', False),
        ('sub1.cname-deny.basic.caatestsuite.com', 'Tests handling of CNAME, where parent is CNAME and CAA record is at target', False),
        ('permit.basic.caatestsuite.com', 'Tests acceptance when name contains a permissible CAA record set', False),
        ('deny.permit.basic.caatestsuite.com', 'Tests acceptance on a CAA record set', False),
    ])
    def api_should_return_is_valid_true_for_valid_tests_in_caa_test_suite_when_caa_domain_is_caatestsuite_com(self, api_client, domain_or_ip_target,
                                                                                                              purpose_of_test, is_wildcard_domain):
        print(f"Running test for {domain_or_ip_target} ({purpose_of_test})")
        if is_wildcard_domain:
            domain_or_ip_target = "*." + domain_or_ip_target
        request = MpicCaaRequest(
            domain_or_ip_target=domain_or_ip_target,
            orchestration_parameters=MpicRequestOrchestrationParameters(perspective_count=3, quorum_count=2),
            caa_check_parameters=CaaCheckParameters(
                certificate_type=CertificateType.TLS_SERVER, caa_domains=['caatestsuite.com', 'example.com'])
        )
        response = api_client.post(MPIC_REQUEST_PATH, json.dumps(request.model_dump()))
        mpic_response = self.mpic_response_adapter.validate_json(response.text)
        assert mpic_response.is_valid is True

    @pytest.mark.skip(reason='Behavior not required in RFC 8659')
    @pytest.mark.parametrize('domain_or_ip_target, purpose_of_test', [
        ('dname-deny.basic.caatestsuite.com', 'Tests handling of a DNAME when CAA record exists at DNAME target'),
        ('cname-deny-sub.basic.caatestsuite.com', 'Tests handling of a CNAME when CAA record exists at parent of CNAME target')
    ])
    def api_should_return_is_valid_false_for_do_not_issue_caa_test_suite_for_rfc_6844(self, api_client, domain_or_ip_target, purpose_of_test):
        print(f"Running test for {domain_or_ip_target} ({purpose_of_test})")
        request = MpicCaaRequest(
            domain_or_ip_target=domain_or_ip_target,
            orchestration_parameters=MpicRequestOrchestrationParameters(perspective_count=3, quorum_count=2),
            caa_check_parameters=CaaCheckParameters(certificate_type=CertificateType.TLS_SERVER, caa_domains=['example.com'])
        )
        response = api_client.post(MPIC_REQUEST_PATH, json.dumps(request.model_dump()))
        mpic_response = self.mpic_response_adapter.validate_json(response.text)
        assert mpic_response.is_valid is False

    @pytest.mark.parametrize('domain_or_ip_target, purpose_of_test', [
        ('dns-01.integration-testing.open-mpic.org', 'Standard proper dns-01 test'),
        ('dns-01-multi.integration-testing.open-mpic.org', 'Proper dns-01 test with multiple TXT records'),
        ('dns-01-cname.integration-testing.open-mpic.org', 'Proper dns-01 test with CNAME')
    ])
    def api_should_return_200_given_valid_dns_01_validation(self, api_client, domain_or_ip_target, purpose_of_test):
        print(f"Running test for {domain_or_ip_target} ({purpose_of_test})")
        request = MpicDcvRequest(
            domain_or_ip_target=domain_or_ip_target,
            orchestration_parameters=MpicRequestOrchestrationParameters(perspective_count=3, quorum_count=2),
            dcv_check_parameters=DcvCheckParameters(
                validation_details=DcvAcmeDns01ValidationDetails(key_authorization="7FwkJPsKf-TH54wu4eiIFA3nhzYaevsL7953ihy-tpo")
            )
        )

        print("\nRequest:\n", json.dumps(request.model_dump(), indent=4))  # pretty print request body
        response = api_client.post(MPIC_REQUEST_PATH, json.dumps(request.model_dump()))
        assert response.status_code == 200
        mpic_response = self.mpic_response_adapter.validate_json(response.text)
        
        assert mpic_response.is_valid is True

    @pytest.mark.parametrize('domain_or_ip_target, purpose_of_test', [
        ('dns-01-leading-whitespace.integration-testing.open-mpic.org', 'leading whitespace'),
        ('dns-01-trailing-whitespace.integration-testing.open-mpic.org', 'trailing'),
        ('dns-01-nxdomain.integration-testing.open-mpic.org', 'NXDOMAIN')
    ])
    def api_should_return_200_is_valid_false_given_invalid_dns_01_validation(self, api_client, domain_or_ip_target, purpose_of_test):
        print(f"Running test for {domain_or_ip_target} ({purpose_of_test})")
        request = MpicDcvRequest(
            domain_or_ip_target=domain_or_ip_target,
            orchestration_parameters=MpicRequestOrchestrationParameters(perspective_count=3, quorum_count=2),
            dcv_check_parameters=DcvCheckParameters(
                validation_details=DcvAcmeDns01ValidationDetails(key_authorization="7FwkJPsKf-TH54wu4eiIFA3nhzYaevsL7953ihy-tpo")
            )
        )

        print("\nRequest:\n", json.dumps(request.model_dump(), indent=4))  # pretty print request body
        response = api_client.post(MPIC_REQUEST_PATH, json.dumps(request.model_dump()))
        assert response.status_code == 200
        mpic_response = self.mpic_response_adapter.validate_json(response.text)
        
        assert mpic_response.is_valid is False

    @pytest.mark.parametrize('domain_or_ip_target, dns_record_type, challenge_value, purpose_of_test', [
        ('dns-change-txt.integration-testing.open-mpic.org', DnsRecordType.TXT, "1234567890abcdefg.", 'standard TXT dns change'),
        ('dns-change-cname.integration-testing.open-mpic.org', DnsRecordType.CNAME, "1234567890abcdefg.", 'standard CNAME dns change'),
        ('dns-change-caa.integration-testing.open-mpic.org', DnsRecordType.CAA, '0 dnschange "1234567890abcdefg."', 'standard CAA dns change'),
    ])
    def api_should_return_200_is_valid_true_given_valid_dns_change_validation(self, api_client, domain_or_ip_target, dns_record_type, challenge_value, purpose_of_test):
        print(f"Running test for {domain_or_ip_target} ({purpose_of_test})")
        request = MpicDcvRequest(
            domain_or_ip_target=domain_or_ip_target,
            orchestration_parameters=MpicRequestOrchestrationParameters(perspective_count=3, quorum_count=2),
            dcv_check_parameters=DcvCheckParameters(
                validation_details=DcvDnsChangeValidationDetails(challenge_value=challenge_value, dns_record_type=dns_record_type, dns_name_prefix="")
            )
        )

        print("\nRequest:\n", json.dumps(request.model_dump(), indent=4))  # pretty print request body
        response = api_client.post(MPIC_REQUEST_PATH, json.dumps(request.model_dump()))
        assert response.status_code == 200
        print("\nResponse:\n", json.dumps(json.loads(response.text), indent=4))  # pretty print request body
        
        mpic_response = self.mpic_response_adapter.validate_json(response.text)
        
        assert mpic_response.is_valid is True

    def api_should_return_200_and_failed_corroboration_given_failed_dcv_check(self, api_client):
        request = MpicDcvRequest(
            domain_or_ip_target='ifconfig.me',
            dcv_check_parameters=DcvCheckParameters(
                validation_details=DcvWebsiteChangeValidationDetails(http_token_path='/',
                                                                     challenge_value='test')
            )
        )

        print("\nRequest:\n", json.dumps(request.model_dump(), indent=4))  # pretty print request body
        response = api_client.post(MPIC_REQUEST_PATH, json.dumps(request.model_dump()))
        assert response.status_code == 200
        response_body = json.loads(response.text)
        print("\nResponse:\n", json.dumps(response_body, indent=4))  # pretty print response body

    def api_should_return_400_given_invalid_orchestration_parameters_in_request(self, api_client):
        request = MpicCaaRequest(
            domain_or_ip_target='example.com',
            orchestration_parameters=MpicRequestOrchestrationParameters(perspective_count=3, quorum_count=5),  # invalid quorum count
            caa_check_parameters=CaaCheckParameters(certificate_type=CertificateType.TLS_SERVER, caa_domains=['mozilla.com'])
        )

        print("\nRequest:\n", json.dumps(request.model_dump(), indent=4))  # pretty print request body
        response = api_client.post(MPIC_REQUEST_PATH, json.dumps(request.model_dump()))
        assert response.status_code == 400
        response_body = json.loads(response.text)
        print("\nResponse:\n", json.dumps(response_body, indent=4))  # pretty print response body
        assert response_body['error'] == MpicRequestValidationMessages.REQUEST_VALIDATION_FAILED.key
        assert any(issue['issue_type'] == MpicRequestValidationMessages.INVALID_QUORUM_COUNT.key for issue in response_body['validation_issues'])

    def api_should_return_400_given_invalid_check_type_in_request(self, api_client):
        request = MpicCaaRequest(
            domain_or_ip_target='example.com',
            orchestration_parameters=MpicRequestOrchestrationParameters(perspective_count=3, quorum_count=2),
            caa_check_parameters=CaaCheckParameters(certificate_type=CertificateType.TLS_SERVER, caa_domains=['mozilla.com'])
        )
        request.check_type = 'invalid_check_type'

        print("\nRequest:\n", json.dumps(request.model_dump(), indent=4))  # pretty print request body
        response = api_client.post(MPIC_REQUEST_PATH, json.dumps(request.model_dump()))
        assert response.status_code == 400
        response_body = json.loads(response.text)
        print("\nResponse:\n", json.dumps(response_body, indent=4))
        assert response_body['error'] == MpicRequestValidationMessages.REQUEST_VALIDATION_FAILED.key
