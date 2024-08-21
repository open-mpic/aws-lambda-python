import json
import pydantic
import pytest
from aws_lambda_python.common_domain.dcv_validation_method import DcvValidationMethod
from aws_lambda_python.mpic_coordinator.domain.mpic_dcv_request import MpicDcvRequest

from valid_request_creator import ValidRequestCreator


# noinspection PyMethodMayBeStatic
class TestMpicDcvRequest:
    def from_json__should_return_dcv_mpic_request_given_valid_dcv_json(self):
        body = ValidRequestCreator.create_valid_dcv_check_request_body()
        json_body = json.dumps(body)
        mpic_request = MpicDcvRequest.from_json(json_body)
        assert mpic_request.orchestration_parameters.domain_or_ip_target == body['orchestration_parameters']['domain_or_ip_target']

    def from_json__should_throw_validation_error_given_missing_orchestration_parameters(self):
        body = ValidRequestCreator.create_valid_dcv_check_request_body()
        del body['orchestration_parameters']
        json_body = json.dumps(body)
        with pytest.raises(pydantic.ValidationError) as validation_error:
            MpicDcvRequest.from_json(json_body)
        assert 'orchestration_parameters' in str(validation_error.value)

    # TODO this is probably not a valid test given that perspectives are for diagnostics mode only
    # it likely needs different logic overall
    def from_json__should_throw_validation_error_given_both_perspectives_and_perspective_count_present(self):
        body = ValidRequestCreator.create_valid_dcv_check_request_body()
        body['orchestration_parameters']['perspective_count'] = 1
        body['orchestration_parameters']['perspectives'] = ['test']
        json_body = json.dumps(body)
        with pytest.raises(pydantic.ValidationError) as validation_error:
            MpicDcvRequest.from_json(json_body)
        assert 'perspective_count' in str(validation_error.value)
        assert 'perspectives' in str(validation_error.value)

    def from_json__should_throw_validation_error_given_missing_dcv_details(self):
        body = ValidRequestCreator.create_valid_dcv_check_request_body()
        del body['dcv_details']
        json_body = json.dumps(body)
        with pytest.raises(pydantic.ValidationError) as validation_error:
            MpicDcvRequest.from_json(json_body)
        assert 'dcv_details' in str(validation_error.value)

    def from_json__should_throw_validation_error_given_missing_validation_method(self):
        body = ValidRequestCreator.create_valid_dcv_check_request_body()
        del body['dcv_details']['validation_method']
        json_body = json.dumps(body)
        with pytest.raises(pydantic.ValidationError) as validation_error:
            MpicDcvRequest.from_json(json_body)
        assert 'validation_method' in str(validation_error.value)

    def from_json__should_throw_validation_error_given_invalid_validation_method(self):
        body = ValidRequestCreator.create_valid_dcv_check_request_body()
        body['dcv_details']['validation_method'] = 'invalid'
        json_body = json.dumps(body)
        with pytest.raises(pydantic.ValidationError) as validation_error:
            MpicDcvRequest.from_json(json_body)
        assert 'validation_method' in str(validation_error.value)
        assert 'invalid' in str(validation_error.value)

    def from_json__should_throw_validation_error_given_missing_validation_details(self):
        body = ValidRequestCreator.create_valid_dcv_check_request_body()
        del body['dcv_details']['validation_details']
        json_body = json.dumps(body)
        with pytest.raises(pydantic.ValidationError) as validation_error:
            MpicDcvRequest.from_json(json_body)
        assert 'validation_details' in str(validation_error.value)

    def from_json__should_throw_validation_error_given_missing_expected_challenge(self):
        body = ValidRequestCreator.create_valid_dcv_check_request_body()
        del body['dcv_details']['validation_details']['expected_challenge']
        json_body = json.dumps(body)
        with pytest.raises(pydantic.ValidationError) as validation_error:
            MpicDcvRequest.from_json(json_body)
        assert 'expected_challenge' in str(validation_error.value)

    def from_json__should_throw_validation_error_given_missing_prefix_for_dns_validation(self):
        body = ValidRequestCreator.create_valid_dcv_check_request_body(DcvValidationMethod.DNS_GENERIC)
        del body['dcv_details']['validation_details']['prefix']
        json_body = json.dumps(body)
        with pytest.raises(pydantic.ValidationError) as validation_error:
            MpicDcvRequest.from_json(json_body)
        assert 'prefix' in str(validation_error.value)

    def from_json__should_throw_validation_error_given_missing_record_type_for_dns_validation(self):
        body = ValidRequestCreator.create_valid_dcv_check_request_body(DcvValidationMethod.DNS_GENERIC)
        del body['dcv_details']['validation_details']['record_type']
        json_body = json.dumps(body)
        with pytest.raises(pydantic.ValidationError) as validation_error:
            MpicDcvRequest.from_json(json_body)
        assert 'record_type' in str(validation_error.value)

    def from_json__should_throw_validation_error_given_invalid_record_type_for_dns_validation(self):
        body = ValidRequestCreator.create_valid_dcv_check_request_body(DcvValidationMethod.DNS_GENERIC)
        body['dcv_details']['validation_details']['record_type'] = 'invalid'
        json_body = json.dumps(body)
        with pytest.raises(pydantic.ValidationError) as validation_error:
            MpicDcvRequest.from_json(json_body)
        assert 'record_type' in str(validation_error.value)
        assert 'invalid' in str(validation_error.value)

    def from_json__should_throw_validation_error_given_missing_path_for_http_validation(self):
        body = ValidRequestCreator.create_valid_dcv_check_request_body(DcvValidationMethod.HTTP_GENERIC)
        del body['dcv_details']['validation_details']['path']
        json_body = json.dumps(body)
        with pytest.raises(pydantic.ValidationError) as validation_error:
            MpicDcvRequest.from_json(json_body)
        assert 'path' in str(validation_error.value)


if __name__ == '__main__':
    pytest.main()
