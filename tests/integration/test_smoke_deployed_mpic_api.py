import json
import sys
import pytest

from pydantic import TypeAdapter

from open_mpic_core import (
    CaaCheckParameters,
    DcvAcmeDns01ValidationParameters,
)
from open_mpic_core import CertificateType
from open_mpic_core import MpicCaaRequest, MpicDcvRequest, MpicResponse
from open_mpic_core import MpicRequestOrchestrationParameters

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

    def api__should_return_200_and_passed_corroboration_for_successful_caa_check(self, api_client):
        request = MpicCaaRequest(
            domain_or_ip_target="example.com",
            orchestration_parameters=MpicRequestOrchestrationParameters(perspective_count=3, quorum_count=2),
            caa_check_parameters=CaaCheckParameters(
                certificate_type=CertificateType.TLS_SERVER, caa_domains=["mozilla.com"]
            ),
        )

        print("\nRequest:\n", json.dumps(request.model_dump(), indent=4))  # pretty print request body
        response = api_client.post(MPIC_REQUEST_PATH, json.dumps(request.model_dump()))
        self.validate_200_response(response)

    def api__should_return_200_and_successful_corroboration_for_valid_dns_01_validation(self, api_client):
        request = MpicDcvRequest(
            domain_or_ip_target='dns-01.integration-testing.open-mpic.org',
            orchestration_parameters=MpicRequestOrchestrationParameters(perspective_count=3, quorum_count=2),
            dcv_check_parameters=DcvAcmeDns01ValidationParameters(
                key_authorization_hash="7FwkJPsKf-TH54wu4eiIFA3nhzYaevsL7953ihy-tpo"
            ),
        )

        print("\nRequest:\n", json.dumps(request.model_dump(), indent=4))  # pretty print request body
        response = api_client.post(MPIC_REQUEST_PATH, json.dumps(request.model_dump()))
        self.validate_200_response(response)

    def validate_200_response(self, response):
        assert response.status_code == 200
        mpic_response = self.mpic_response_adapter.validate_json(response.text)
        print("\nResponse:\n", json.dumps(mpic_response.model_dump(), indent=4))
        assert mpic_response.is_valid is True
