import json
import sys
import pytest
import testing_api_client


# noinspection PyMethodMayBeStatic
@pytest.mark.integration
class TestDeployedMpicApi:
    def api_should_return_200_given_valid_authentication(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", sys.argv[:1])  # blank out argv except for first param; arg parser doesn't expect pytest args

        api_client = testing_api_client.TestingApiClient()
        payload = {
            "api-version": "1.0.0",
            "system-params": {
                "identifier": "test",
                "perspective-count": 3,
                "quorum-count": 2
            },
            "caa-details": {
                "caa-domains": [
                    "mozilla.com"
                ]
            }
        }
        payload_as_string = json.dumps(payload)
        response = api_client.post("caa-check", payload_as_string)
        api_client.close()
        # response_body_as_json = response.json()
        assert response.status_code == 200
