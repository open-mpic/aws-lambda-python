import json
import sys
import pytest
import testing_api_client


# noinspection PyMethodMayBeStatic
@pytest.mark.integration
class TestDeployedMpicApi:
    def api_should_return_200_given_valid_authentication(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", sys.argv[:1])  # blank out argv except for first param; arg parser doesn't expect pytest args
        perspective_count = 3

        api_client = testing_api_client.TestingApiClient()
        body = {
            "api-version": "1.0.0",
            "system-params": {
                "identifier": "test",
                "perspective-count": perspective_count,
                "quorum-count": 2
            },
            "caa-details": {
                "caa-domains": [
                    "mozilla.com"
                ]
            }
        }
        response = api_client.post("caa-check", json.dumps(body))
        api_client.close()
        # response_body_as_json = response.json()
        assert response.status_code == 200
        # assert response body has a list of perspectives with length 2, and each element has response code 200
        response_body = json.loads(response.text)
        perspectives_list = response_body["perspectives"]  # each element is a dictionary with 'statusCode' element
        # assert that each element in perspectives_list has a 'statusCode' element with value 200
        assert len(perspectives_list) == perspective_count
        assert len(list(filter(lambda perspective: perspective["statusCode"] == 200, perspectives_list))) == perspective_count
