import json
import sys
import pytest

from pydantic import TypeAdapter

from open_mpic_core import (
    CaaCheckParameters,
    DcvWebsiteChangeValidationParameters,
    DcvAcmeDns01ValidationParameters,
    DcvAcmeHttp01ValidationParameters,
    DcvDnsChangeValidationParameters,
)
from open_mpic_core import CertificateType, CheckType, DnsRecordType
from open_mpic_core import MpicCaaRequest, MpicDcvRequest, MpicResponse, PerspectiveResponse
from open_mpic_core import MpicRequestOrchestrationParameters, MpicEffectiveOrchestrationParameters
from open_mpic_core import MpicRequestValidationMessages
from open_mpic_core import DcvCheckResponse, DcvDnsCheckResponseDetails, DcvValidationMethod
from open_mpic_core import CaaCheckResponse, CaaCheckResponseDetails

import testing_api_client


MPIC_REQUEST_PATH = "/mpic"


# noinspection PyMethodMayBeStatic
@pytest.mark.integration
class TestDeployedMpicApi:
    @classmethod
    def setup_class(cls):
        cls.mpic_response_adapter = TypeAdapter(MpicResponse)

    @pytest.fixture(scope="class")
    def api_client(self):
        with pytest.MonkeyPatch.context() as class_scoped_monkeypatch:
            # blank out argv except first param; arg parser doesn't expect pytest args
            class_scoped_monkeypatch.setattr(sys, "argv", sys.argv[:1])
            api_client = testing_api_client.TestingApiClient()
            yield api_client
            api_client.close()

    def api__should_return_successful_corroboration_with_check_details_for_successful_caa_check(self, api_client):
        request = MpicCaaRequest(
            domain_or_ip_target="example.com",
            orchestration_parameters=MpicRequestOrchestrationParameters(perspective_count=3, quorum_count=2),
            caa_check_parameters=CaaCheckParameters(
                certificate_type=CertificateType.TLS_SERVER, caa_domains=["mozilla.com"]
            ),
        )

        response = api_client.post(MPIC_REQUEST_PATH, json.dumps(request.model_dump()))
        assert response.status_code == 200
        mpic_response = self.mpic_response_adapter.validate_json(response.text)

        # Verify base response structure
        assert mpic_response.is_valid is True
        assert mpic_response.mpic_completed is True
        assert mpic_response.check_type == CheckType.CAA
        assert mpic_response.domain_or_ip_target == request.domain_or_ip_target
        assert isinstance(mpic_response.request_orchestration_parameters, MpicRequestOrchestrationParameters)
        assert isinstance(mpic_response.actual_orchestration_parameters, MpicEffectiveOrchestrationParameters)
        assert isinstance(mpic_response.perspectives, list)
        perspectives_list: list[PerspectiveResponse] = mpic_response.perspectives
        assert len(perspectives_list) >= request.orchestration_parameters.perspective_count

        # Verify each perspective response
        for perspective in perspectives_list:
            assert isinstance(perspective.perspective_code, str)
            assert isinstance(perspective.check_response, CaaCheckResponse)

            # Verify check response
            check_response = perspective.check_response
            assert check_response.check_completed is True
            assert check_response.check_passed is True
            assert check_response.check_type == CheckType.CAA
            assert check_response.errors is None or len(check_response.errors) == 0
            assert isinstance(check_response.timestamp_ns, int)

            # Verify CAA check details
            details = check_response.details
            assert isinstance(details, CaaCheckResponseDetails)
            assert isinstance(details.caa_record_present, bool) or details.caa_record_present is None
            assert isinstance(details.found_at, str) or details.found_at is None
            assert isinstance(details.records_seen, list) or details.records_seen is None

    # fmt: on
    def api__should_return_successful_corroboration_with_check_details_for_valid_dns_01_validation(self, api_client):
        domain_or_ip_target = 'dns-01.integration-testing.open-mpic.org'
        request = MpicDcvRequest(
            domain_or_ip_target=domain_or_ip_target,
            orchestration_parameters=MpicRequestOrchestrationParameters(perspective_count=3, quorum_count=2),
            dcv_check_parameters=DcvAcmeDns01ValidationParameters(
                key_authorization_hash="7FwkJPsKf-TH54wu4eiIFA3nhzYaevsL7953ihy-tpo"
            ),
        )

        print("\nRequest:\n", json.dumps(request.model_dump(), indent=4))  # pretty print request body
        response = api_client.post(MPIC_REQUEST_PATH, json.dumps(request.model_dump()))
        assert response.status_code == 200
        mpic_response = self.mpic_response_adapter.validate_json(response.text)
        assert mpic_response.is_valid is True
        assert mpic_response.mpic_completed is True
        assert mpic_response.check_type == CheckType.DCV
        assert mpic_response.domain_or_ip_target == domain_or_ip_target
        assert isinstance(mpic_response.request_orchestration_parameters, MpicRequestOrchestrationParameters)
        assert isinstance(mpic_response.actual_orchestration_parameters, MpicEffectiveOrchestrationParameters)
        assert isinstance(mpic_response.perspectives, list)
        assert len(mpic_response.perspectives) >= mpic_response.request_orchestration_parameters.perspective_count

        # Verify each perspective response
        for perspective in mpic_response.perspectives:
            assert isinstance(perspective.perspective_code, str)
            assert isinstance(perspective.check_response, DcvCheckResponse)

            # Verify check response
            check_response = perspective.check_response
            assert check_response.check_completed is True
            assert check_response.check_passed is True
            assert check_response.check_type == CheckType.DCV
            assert check_response.errors is None or len(check_response.errors) == 0
            assert isinstance(check_response.timestamp_ns, int)

            # Verify DNS check details
            details = check_response.details
            assert isinstance(details, DcvDnsCheckResponseDetails)
            assert details.validation_method == DcvValidationMethod.ACME_DNS_01
            assert isinstance(details.records_seen, list)
            assert isinstance(details.response_code, int)
            assert isinstance(details.ad_flag, bool) or details.ad_flag is None
            assert isinstance(details.found_at, str) or details.found_at is None

    # fmt: off
    @pytest.mark.parametrize('domain_or_ip_target, purpose_of_test', [
        ('dns-01.integration-testing.open-mpic.org', 'Standard proper dns-01 test'),
        ('dns-01-multi.integration-testing.open-mpic.org', 'Proper dns-01 test with multiple TXT records'),
        ('dns-01-cname.integration-testing.open-mpic.org', 'Proper dns-01 test with CNAME')
    ])
    # fmt: on
    def api__should_return_successful_corroboration_for_valid_dns_01_validation_of_various_dns_record_types(
        self, api_client, domain_or_ip_target, purpose_of_test
    ):
        print(f"Running test for {domain_or_ip_target} ({purpose_of_test})")
        request = MpicDcvRequest(
            domain_or_ip_target=domain_or_ip_target,
            orchestration_parameters=MpicRequestOrchestrationParameters(perspective_count=3, quorum_count=2),
            dcv_check_parameters=DcvAcmeDns01ValidationParameters(
                key_authorization_hash="7FwkJPsKf-TH54wu4eiIFA3nhzYaevsL7953ihy-tpo"
            ),
        )

        print("\nRequest:\n", json.dumps(request.model_dump(), indent=4))  # pretty print request body
        response = api_client.post(MPIC_REQUEST_PATH, json.dumps(request.model_dump()))
        assert response.status_code == 200
        mpic_response = self.mpic_response_adapter.validate_json(response.text)
        assert mpic_response.is_valid is True
        assert mpic_response.mpic_completed is True

    # fmt: off
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
    # fmt: on
    def api__should_return_failed_corroboration_for_all_tests_in_do_not_issue_caa_test_suite(
        self, api_client, domain_or_ip_target, purpose_of_test, is_wildcard_domain
    ):
        print(f"Running test for {domain_or_ip_target} ({purpose_of_test})")
        if is_wildcard_domain:
            domain_or_ip_target = "*." + domain_or_ip_target
        request = MpicCaaRequest(
            domain_or_ip_target=domain_or_ip_target,
            orchestration_parameters=MpicRequestOrchestrationParameters(perspective_count=3, quorum_count=2),
            caa_check_parameters=CaaCheckParameters(
                certificate_type=CertificateType.TLS_SERVER, caa_domains=["example.com"]
            ),
        )
        response = api_client.post(MPIC_REQUEST_PATH, json.dumps(request.model_dump()))
        mpic_response = self.mpic_response_adapter.validate_json(response.text)
        assert mpic_response.is_valid is False

    # NOTE: Open MPIC AWS-Lambda-Python currently is not able to communicate with an IPv6 only nameserver.
    # This case is handled in a compliant manner as it is treated as a lookup failure.
    # The test for proper communication with an IPv6 nameserver can be enabled with the following additional parameter to the list below.
    # ('ipv6only.caatestsuite.com', 'Tests handling of record at IPv6-only authoritative name server', False),
    # fmt: off
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
    # fmt: on
    def api__should_return_successful_corroboration_for_caa_test_suite_when_caa_domain_is_caatestsuite_com(
        self, api_client, domain_or_ip_target, purpose_of_test, is_wildcard_domain
    ):
        print(f"Running test for {domain_or_ip_target} ({purpose_of_test})")
        if is_wildcard_domain:
            domain_or_ip_target = "*." + domain_or_ip_target
        request = MpicCaaRequest(
            domain_or_ip_target=domain_or_ip_target,
            orchestration_parameters=MpicRequestOrchestrationParameters(perspective_count=3, quorum_count=2),
            caa_check_parameters=CaaCheckParameters(
                certificate_type=CertificateType.TLS_SERVER, caa_domains=["caatestsuite.com", "example.com"]
            ),
        )
        response = api_client.post(MPIC_REQUEST_PATH, json.dumps(request.model_dump()))
        mpic_response = self.mpic_response_adapter.validate_json(response.text)
        assert mpic_response.is_valid is True

    @pytest.mark.skip(reason="Behavior not required in RFC 8659")
    # fmt: off
    @pytest.mark.parametrize('domain_or_ip_target, purpose_of_test', [
        ('dname-deny.basic.caatestsuite.com', 'Tests handling of a DNAME when CAA record exists at DNAME target'),
        ('cname-deny-sub.basic.caatestsuite.com', 'Tests handling of a CNAME when CAA record exists at parent of CNAME target')
    ])
    # fmt: on
    def api__should_return_is_valid_false_for_do_not_issue_caa_test_suite_for_rfc_6844(
        self, api_client, domain_or_ip_target, purpose_of_test
    ):
        print(f"Running test for {domain_or_ip_target} ({purpose_of_test})")
        request = MpicCaaRequest(
            domain_or_ip_target=domain_or_ip_target,
            orchestration_parameters=MpicRequestOrchestrationParameters(perspective_count=3, quorum_count=2),
            caa_check_parameters=CaaCheckParameters(
                certificate_type=CertificateType.TLS_SERVER, caa_domains=["example.com"]
            ),
        )
        response = api_client.post(MPIC_REQUEST_PATH, json.dumps(request.model_dump()))
        mpic_response = self.mpic_response_adapter.validate_json(response.text)
        assert mpic_response.is_valid is False

    # fmt: off
    @pytest.mark.parametrize('domain_or_ip_target, purpose_of_test', [
        ('dns-01-leading-whitespace.integration-testing.open-mpic.org', 'leading whitespace'),
        ('dns-01-trailing-whitespace.integration-testing.open-mpic.org', 'trailing'),
        ('dns-01-nxdomain.integration-testing.open-mpic.org', 'NXDOMAIN')
    ])
    # fmt: on
    def api__should_return_200_and_failed_corroboration_for_invalid_dns_01_validation(
        self, api_client, domain_or_ip_target, purpose_of_test
    ):
        print(f"Running test for {domain_or_ip_target} ({purpose_of_test})")
        request = MpicDcvRequest(
            domain_or_ip_target=domain_or_ip_target,
            orchestration_parameters=MpicRequestOrchestrationParameters(perspective_count=3, quorum_count=2),
            dcv_check_parameters=DcvAcmeDns01ValidationParameters(
                key_authorization_hash="7FwkJPsKf-TH54wu4eiIFA3nhzYaevsL7953ihy-tpo"
            ),
        )

        print("\nRequest:\n", json.dumps(request.model_dump(), indent=4))  # pretty print request body
        response = api_client.post(MPIC_REQUEST_PATH, json.dumps(request.model_dump()))
        assert response.status_code == 200
        mpic_response = self.mpic_response_adapter.validate_json(response.text)

        assert mpic_response.is_valid is False

    # fmt: off
    @pytest.mark.parametrize('domain_or_ip_target, purpose_of_test, token, key_authorization', [
        ('integration-testing.open-mpic.org', 'Standard http-01 test', "evaGxfADs6pSRb2LAv9IZf17Dt3juxGJ-PCt92wr-oA", "evaGxfADs6pSRb2LAv9IZf17Dt3juxGJ-PCt92wr-oA.NzbLsXh8uDCcd-6MNwXF4W_7noWXFZAfHkxZsRGC9Xs"),
        ('integration-testing.open-mpic.org', 'Redirect 302 http-01 test', "evaGxfADs6pSRb2LAv9IZf17Dt3juxGJ-PCt92wr-oB", "evaGxfADs6pSRb2LAv9IZf17Dt3juxGJ-PCt92wr-oA.NzbLsXh8uDCcd-6MNwXF4W_7noWXFZAfHkxZsRGC9Xs")
    ])
    # fmt: on
    def api__should_return_200_and_successful_corroboration_for_valid_http_01_validation(
        self, api_client, domain_or_ip_target, purpose_of_test, token, key_authorization
    ):
        print(f"Running test for {domain_or_ip_target} ({purpose_of_test})")
        request = MpicDcvRequest(
            domain_or_ip_target=domain_or_ip_target,
            orchestration_parameters=MpicRequestOrchestrationParameters(perspective_count=3, quorum_count=2),
            dcv_check_parameters=DcvAcmeHttp01ValidationParameters(key_authorization=key_authorization, token=token),
        )
        print("\nRequest:\n", json.dumps(request.model_dump(), indent=4))  # pretty print request body
        response = api_client.post(MPIC_REQUEST_PATH, json.dumps(request.model_dump()))
        assert response.status_code == 200
        mpic_response = self.mpic_response_adapter.validate_json(response.text)

        assert mpic_response.is_valid is True

    # fmt: off
    @pytest.mark.parametrize('domain_or_ip_target, purpose_of_test, token, key_authorization', [
        ('integration-testing.open-mpic.org', 'Failed http-01 test', "evaGxfADs6pSRb2LAv9IZf17Dt3juxGJ-PCt92wr-oA", "evaGxfADs6pSRb2LAv9IZf17Dt3juxGJ-PCt92wr-oA.NzbLsXh8uDCcd-6MNwXF4W_7noWXFZAfHkxZsRGC9Xa"),
        ('integration-testing.open-mpic.org', 'Failed 302 http-01 test', "evaGxfADs6pSRb2LAv9IZf17Dt3juxGJ-PCt92wr-oB", "evaGxfADs6pSRb2LAv9IZf17Dt3juxGJ-PCt92wr-oA.NzbLsXh8uDCcd-6MNwXF4W_7noWXFZAfHkxZsRGC9Xa")
    ])
    # fmt: on
    def api__should_return_200_and_failed_corroboration_for_invalid_dns_01_validation(
        self, api_client, domain_or_ip_target, purpose_of_test, token, key_authorization
    ):
        print(f"Running test for {domain_or_ip_target} ({purpose_of_test})")
        request = MpicDcvRequest(
            domain_or_ip_target=domain_or_ip_target,
            orchestration_parameters=MpicRequestOrchestrationParameters(perspective_count=3, quorum_count=2),
            dcv_check_parameters=DcvAcmeDns01ValidationParameters(
                key_authorization_hash="7FwkJPsKf-TH54wu4eiIFA3nhzYaevsL7953ihy-tpo"
            ),
        )

        print("\nRequest:\n", json.dumps(request.model_dump(), indent=4))  # pretty print request body
        response = api_client.post(MPIC_REQUEST_PATH, json.dumps(request.model_dump()))
        assert response.status_code == 200
        mpic_response = self.mpic_response_adapter.validate_json(response.text)

        assert mpic_response.is_valid is False

    # fmt: off
    @pytest.mark.parametrize('domain_or_ip_target, purpose_of_test, http_token_path, challenge_value', [
        ('integration-testing.open-mpic.org', 'Valid website change v2 challenge', 'validation-doc.txt', 'test-validation'),
        ('integration-testing.open-mpic.org', 'Valid 302 website change v2 challenge', 'validation-doc-redirect.txt', "test-validation-redirect")
    ])
    # fmt: on
    def api__should_return_200_and_successful_corroboration_for_valid_website_change_validation(
        self, api_client, domain_or_ip_target, purpose_of_test, http_token_path, challenge_value
    ):
        print(f"Running test for {domain_or_ip_target} ({purpose_of_test})")
        request = MpicDcvRequest(
            domain_or_ip_target=domain_or_ip_target,
            orchestration_parameters=MpicRequestOrchestrationParameters(perspective_count=3, quorum_count=2),
            dcv_check_parameters=DcvWebsiteChangeValidationParameters(
                http_token_path=http_token_path, challenge_value=challenge_value
            ),
        )
        print("\nRequest:\n", json.dumps(request.model_dump(), indent=4))  # pretty print request body
        response = api_client.post(MPIC_REQUEST_PATH, json.dumps(request.model_dump()))
        assert response.status_code == 200
        mpic_response = self.mpic_response_adapter.validate_json(response.text)

        assert mpic_response.is_valid is True

    # fmt: off
    @pytest.mark.parametrize('domain_or_ip_target, dns_record_type, challenge_value, purpose_of_test', [
        ('dns-change-txt.integration-testing.open-mpic.org', DnsRecordType.TXT, "1234567890abcdefg.", 'standard TXT dns change'),
        ('dns-change-cname.integration-testing.open-mpic.org', DnsRecordType.CNAME, "1234567890abcdefg.", 'standard CNAME dns change'),
        ('dns-change-caa.integration-testing.open-mpic.org', DnsRecordType.CAA, '1234567890abcdefg.', 'standard CAA dns change'),
    ])
    # fmt: on
    def api__should_return_200_and_successful_corroboration_for_valid_dns_change_validation(
        self, api_client, domain_or_ip_target, dns_record_type, challenge_value, purpose_of_test
    ):
        print(f"Running test for {domain_or_ip_target} ({purpose_of_test})")
        request = MpicDcvRequest(
            domain_or_ip_target=domain_or_ip_target,
            orchestration_parameters=MpicRequestOrchestrationParameters(perspective_count=3, quorum_count=2),
            dcv_check_parameters=DcvDnsChangeValidationParameters(
                challenge_value=challenge_value, dns_record_type=dns_record_type, dns_name_prefix=""
            ),
        )

        print("\nRequest:\n", json.dumps(request.model_dump(), indent=4))  # pretty print request body
        response = api_client.post(MPIC_REQUEST_PATH, json.dumps(request.model_dump()))
        print("\nResponse:\n", json.dumps(json.loads(response.text), indent=4))  # pretty print request body
        assert response.status_code == 200
        mpic_response = self.mpic_response_adapter.validate_json(response.text)
        assert mpic_response.is_valid is True

    def api__should_return_200_and_failed_corroboration_given_failed_dcv_check(self, api_client):
        request = MpicDcvRequest(
            domain_or_ip_target="ifconfig.me",
            dcv_check_parameters=DcvWebsiteChangeValidationParameters(http_token_path="/", challenge_value="test"),
        )

        print("\nRequest:\n", json.dumps(request.model_dump(), indent=4))  # pretty print request body
        response = api_client.post(MPIC_REQUEST_PATH, json.dumps(request.model_dump()))
        assert response.status_code == 200
        response_body = json.loads(response.text)
        print("\nResponse:\n", json.dumps(response_body, indent=4))  # pretty print response body

    def api__should_return_400_given_invalid_orchestration_parameters_in_request(self, api_client):
        request = MpicCaaRequest(
            domain_or_ip_target="example.com",
            orchestration_parameters=MpicRequestOrchestrationParameters(
                perspective_count=3, quorum_count=5
            ),  # invalid quorum count
            caa_check_parameters=CaaCheckParameters(
                certificate_type=CertificateType.TLS_SERVER, caa_domains=["mozilla.com"]
            ),
        )

        print("\nRequest:\n", json.dumps(request.model_dump(), indent=4))  # pretty print request body
        response = api_client.post(MPIC_REQUEST_PATH, json.dumps(request.model_dump()))
        assert response.status_code == 400
        response_body = json.loads(response.text)
        print("\nResponse:\n", json.dumps(response_body, indent=4))  # pretty print response body
        assert response_body["error"] == MpicRequestValidationMessages.REQUEST_VALIDATION_FAILED.key
        assert any(
            issue["issue_type"] == MpicRequestValidationMessages.INVALID_QUORUM_COUNT.key
            for issue in response_body["validation_issues"]
        )

    def api__should_return_400_given_invalid_check_type_in_request(self, api_client):
        request = MpicCaaRequest(
            domain_or_ip_target="example.com",
            orchestration_parameters=MpicRequestOrchestrationParameters(perspective_count=3, quorum_count=2),
            caa_check_parameters=CaaCheckParameters(
                certificate_type=CertificateType.TLS_SERVER, caa_domains=["mozilla.com"]
            ),
        )
        request.check_type = "invalid_check_type"

        print("\nRequest:\n", json.dumps(request.model_dump(), indent=4))  # pretty print request body
        response = api_client.post(MPIC_REQUEST_PATH, json.dumps(request.model_dump()))
        assert response.status_code == 400
        response_body = json.loads(response.text)
        print("\nResponse:\n", json.dumps(response_body, indent=4))
        assert response_body["error"] == MpicRequestValidationMessages.REQUEST_VALIDATION_FAILED.key
