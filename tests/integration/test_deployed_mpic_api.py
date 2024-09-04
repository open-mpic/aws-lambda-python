import json
import sys
import pytest
from aws_lambda_python.common_domain.check_parameters import CaaCheckParameters
from aws_lambda_python.common_domain.check_parameters import DcvCheckParameters, DcvValidationDetails
from aws_lambda_python.common_domain.enum.certificate_type import CertificateType
from aws_lambda_python.common_domain.enum.check_type import CheckType
from aws_lambda_python.common_domain.enum.dcv_validation_method import DcvValidationMethod
from aws_lambda_python.mpic_coordinator.domain.mpic_request import MpicCaaRequest
from aws_lambda_python.mpic_coordinator.domain.mpic_request import MpicDcvRequest
from aws_lambda_python.mpic_coordinator.domain.mpic_orchestration_parameters import MpicRequestOrchestrationParameters
from aws_lambda_python.mpic_coordinator.domain.enum.request_path import RequestPath

import testing_api_client
from aws_lambda_python.mpic_coordinator.messages.mpic_request_validation_messages import MpicRequestValidationMessages


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

    def api_should_return_200_given_and_passed_corroboration_given_successful_caa_check(self, api_client):
        request = MpicCaaRequest(
            domain_or_ip_target='example.com',
            orchestration_parameters=MpicRequestOrchestrationParameters(perspective_count=3, quorum_count=2),
            caa_check_parameters=CaaCheckParameters(certificate_type=CertificateType.TLS_SERVER, caa_domains=['mozilla.com'])
        )

        print("\nRequest:\n", json.dumps(request.model_dump(), indent=4))  # pretty print request body
        response = api_client.post(RequestPath.MPIC, json.dumps(request.model_dump()))
        # response_body_as_json = response.json()
        assert response.status_code == 200
        # assert response body has a list of perspectives with length 2, and each element has response code 200
        response_body = json.loads(response.text)
        print("\nResponse:\n", json.dumps(response_body, indent=4))  # pretty print response body
        perspectives_list = response_body['perspectives']
        assert len(perspectives_list) == request.orchestration_parameters.perspective_count
        assert (len(list(filter(lambda perspective: perspective['check_type'] == CheckType.CAA, perspectives_list)))
                == request.orchestration_parameters.perspective_count)

    @pytest.mark.skip(reason='Not implemented yet')
    def api_should_return_200_given_valid_dcv_validation(self, api_client):
        request = MpicDcvRequest(
            domain_or_ip_target='example.com',
            orchestration_parameters=MpicRequestOrchestrationParameters(perspective_count=3, quorum_count=2),
            dcv_check_parameters=DcvCheckParameters(
                validation_method=DcvValidationMethod.HTTP_GENERIC,
                validation_details=DcvValidationDetails(dns_name_prefix=None, dns_record_type=None, http_token_path='/',
                                                        challenge_value='test')
            )
        )

        print("\nRequest:\n", json.dumps(request.model_dump(), indent=4))  # pretty print request body
        response = api_client.post(RequestPath.MPIC, json.dumps(request.model_dump()))
        assert response.status_code == 200
        response_body = json.loads(response.text)
        print("\nResponse:\n", json.dumps(response_body, indent=4))  # pretty print response body
        # finish test... (and figure out how to actually run it successfully and reliably)

    def api_should_return_200_and_failed_corroboration_given_failed_dcv_check(self, api_client):
        request = MpicDcvRequest(
            domain_or_ip_target='ifconfig.me',
            dcv_check_parameters=DcvCheckParameters(
                validation_method=DcvValidationMethod.HTTP_GENERIC,
                validation_details=DcvValidationDetails(http_token_path='/',
                                                        challenge_value='test')
            )
        )

        print("\nRequest:\n", json.dumps(request.model_dump(), indent=4))  # pretty print request body
        response = api_client.post(RequestPath.MPIC, json.dumps(request.model_dump()))
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
        response = api_client.post(RequestPath.MPIC, json.dumps(request.model_dump()))
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
        response = api_client.post(RequestPath.MPIC, json.dumps(request.model_dump()))
        assert response.status_code == 400
        response_body = json.loads(response.text)
        print("\nResponse:\n", json.dumps(response_body, indent=4))
        assert response_body['error'] == MpicRequestValidationMessages.REQUEST_VALIDATION_FAILED.key