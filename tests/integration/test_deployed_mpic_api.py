import json
import sys
import pytest
import testing_api_client
from aws_lambda_python.mpic_coordinator.messages.validation_messages import ValidationMessages


# noinspection PyMethodMayBeStatic
@pytest.mark.integration
class TestDeployedMpicApi:
    @pytest.fixture(scope='class')
    def api_client(self):
        with pytest.MonkeyPatch.context() as class_scoped_monkeypatch:
            # blank out argv except first param; arg parser doesn't expect pytest args
            class_scoped_monkeypatch.setattr(sys, 'argv', sys.argv[:1])
            api_client = testing_api_client.TestingApiClient()
            yield api_client
            api_client.close()

    def api_should_return_200_given_valid_authentication(self, api_client):
        perspective_count = 3

        body = {
            'api-version': '1.0.0',
            'system-params': {
                'domain-or-ip-target': 'test',
                'perspective-count': perspective_count,
                'quorum-count': 2
            },
            'caa-details': {
                'caa-domains': [
                    'mozilla.com'
                ]
            }
        }
        response = api_client.post('caa-check', json.dumps(body))
        # response_body_as_json = response.json()
        assert response.status_code == 200
        # assert response body has a list of perspectives with length 2, and each element has response code 200
        response_body = json.loads(response.text)
        perspectives_list = response_body['perspectives']  # each element is a dictionary with 'statusCode' element
        # assert that each element in perspectives_list has a 'statusCode' element with value 200
        assert len(perspectives_list) == perspective_count
        assert len(list(filter(lambda perspective: perspective['statusCode'] == 200, perspectives_list))) == perspective_count

    def api_should_return_400_given_invalid_parameters_in_request(self, api_client):
        perspective_count = 3

        body = {
            'api-version': '1.0.0',
            'system-params': {
                'domain-or-ip-target': 'test',
                'perspective-count': perspective_count,
                'quorum-count': 5  # invalid quorum count
            },
            'caa-details': {
                'caa-domains': [
                    'mozilla.com'
                ]
            }
        }
        response = api_client.post('caa-check', json.dumps(body))
        assert response.status_code == 400
        response_body = json.loads(response.text)
        assert response_body['error'] == ValidationMessages.REQUEST_VALIDATION_FAILED.key
        assert any(issue['issue_type'] == ValidationMessages.INVALID_QUORUM_COUNT.key for issue in response_body['validation-issues'])
        