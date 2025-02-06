import requests
import get_api_url
import get_api_key


# not a mock client, but a real client for live API testing
class TestingApiClient:
    def __init__(self):
        self.service_base_url = get_api_url.extract_api_url(None)
        self.api_key = get_api_key.extract_api_key(None)
        print("\nURL: ", self.service_base_url)
        print("\nAPI Key: ", self.api_key)
        self._session = requests.Session()

    def get(self, url_suffix):
        return self._session.get(self.service_base_url + "/" + url_suffix)

    def post(self, url_suffix, data):
        headers = {"content-type": "application/json", "x-api-key": self.api_key}
        response = self._session.post(self.service_base_url + "/" + url_suffix, headers=headers, data=data)
        return response

    def close(self):
        self._session.close()
