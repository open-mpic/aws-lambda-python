import json
import pydantic
import pytest
from aws_lambda_python.mpic_coordinator.domain.mpic_dcv_with_caa_request import MpicDcvWithCaaRequest

from valid_request_creator import ValidRequestCreator


# noinspection PyMethodMayBeStatic
class TestMpicDcvWithCaaRequest:
    def from_json__should_return_dcv_with_caa_mpic_request_given_valid_dcv_with_caa_json(self):
        body = ValidRequestCreator.create_valid_dcv_with_caa_check_request_body()
        json_body = json.dumps(body)
        mpic_request = MpicDcvWithCaaRequest.from_json(json_body)
        assert mpic_request.orchestration_parameters.domain_or_ip_target == body['orchestration_parameters']['domain_or_ip_target']

    def from_json__should_throw_validation_error_given_missing_domain_or_ip_target(self):
        body = ValidRequestCreator.create_valid_dcv_check_request_body()
        del body['orchestration_parameters']['domain_or_ip_target']
        json_body = json.dumps(body)
        with pytest.raises(pydantic.ValidationError) as validation_error:
            MpicDcvWithCaaRequest.from_json(json_body)
        assert 'domain_or_ip_target' in str(validation_error.value)

    def from_json__should_throw_validation_error_given_missing_caa_details(self):
        body = ValidRequestCreator.create_valid_dcv_with_caa_check_request_body()
        del body['caa_details']
        json_body = json.dumps(body)
        with pytest.raises(pydantic.ValidationError) as validation_error:
            MpicDcvWithCaaRequest.from_json(json_body)
        assert 'caa_details' in str(validation_error.value)

    def from_json__should_throw_validation_error_given_missing_dcv_details(self):
        body = ValidRequestCreator.create_valid_dcv_check_request_body()
        del body['dcv_details']
        json_body = json.dumps(body)
        with pytest.raises(pydantic.ValidationError) as validation_error:
            MpicDcvWithCaaRequest.from_json(json_body)
        assert 'dcv_details' in str(validation_error.value)


if __name__ == '__main__':
    pytest.main()