import json
import pydantic
import pytest
from aws_lambda_python.mpic_coordinator.domain.mpic_caa_request import MpicCaaRequest
from aws_lambda_python.mpic_coordinator.domain.mpic_dcv_request import MpicDcvRequest

from valid_request_creator import ValidRequestCreator


# noinspection PyMethodMayBeStatic
class TestMpicCaaRequest:
    """
        Tests correctness of configuration for Pydantic-driven auto validation of MpicCaaRequest objects.
        """

    def from_json__should_return_caa_mpic_request_given_valid_caa_json(self):
        body = ValidRequestCreator.create_valid_caa_check_request_body()
        json_body = json.dumps(body)
        mpic_request = MpicCaaRequest.from_json(json_body)
        assert mpic_request.orchestration_parameters.domain_or_ip_target == body['orchestration_parameters']['domain_or_ip_target']

    # TODO remove when API version in request moves to URL
    def from_json__should_throw_validation_error_given_missing_api_version(self):
        body = ValidRequestCreator.create_valid_caa_check_request_body()
        del body['api_version']
        json_body = json.dumps(body)
        with pytest.raises(pydantic.ValidationError) as validation_error:
            MpicCaaRequest.from_json(json_body)
        assert 'api_version' in str(validation_error.value)

    def from_json__should_throw_validation_error_given_missing_orchestration_parameters(self):
        body = ValidRequestCreator.create_valid_dcv_check_request_body()
        del body['orchestration_parameters']
        json_body = json.dumps(body)
        with pytest.raises(pydantic.ValidationError) as validation_error:
            MpicDcvRequest.from_json(json_body)
        assert 'orchestration_parameters' in str(validation_error.value)

    def from_json__should_throw_validation_error_given_missing_domain_or_ip_target(self):
        body = ValidRequestCreator.create_valid_caa_check_request_body()
        del body['orchestration_parameters']['domain_or_ip_target']
        json_body = json.dumps(body)
        with pytest.raises(pydantic.ValidationError) as validation_error:
            MpicCaaRequest.from_json(json_body)
        assert 'domain_or_ip_target' in str(validation_error.value)

    # TODO are caa_details necessary? (domain list, certificate type)
    def from_json__should_throw_validation_error_given_missing_caa_details(self):
        body = ValidRequestCreator.create_valid_caa_check_request_body()
        del body['caa_details']
        json_body = json.dumps(body)
        with pytest.raises(pydantic.ValidationError) as validation_error:
            MpicCaaRequest.from_json(json_body)
        assert 'caa_details' in str(validation_error.value)
        assert 'missing' in str(validation_error.value)

    def from_json_should_throw_validation_error_given_invalid_certificate_type(self):
        body = ValidRequestCreator.create_valid_caa_check_request_body()
        body['caa_details']['certificate_type'] = 'invalid'
        json_body = json.dumps(body)
        with pytest.raises(pydantic.ValidationError) as validation_error:
            MpicCaaRequest.from_json(json_body)
        assert 'certificate_type' in str(validation_error.value)
        assert 'invalid' in str(validation_error.value)


if __name__ == '__main__':
    pytest.main()
