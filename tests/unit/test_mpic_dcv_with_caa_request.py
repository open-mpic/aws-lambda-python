import json
import pydantic
import pytest
from aws_lambda_python.common_domain.enum.check_type import CheckType
from aws_lambda_python.mpic_coordinator.domain.mpic_request import MpicDcvWithCaaRequest

from valid_request_creator import ValidRequestCreator


# noinspection PyMethodMayBeStatic
class TestMpicDcvWithCaaRequest:
    """
        Tests correctness of configuration for Pydantic-driven auto validation of MpicDcvWithCaaRequest objects.
        """

    def model_validate_json__should_return_valid_instance_given_valid_dcv_with_caa_json(self):
        request = ValidRequestCreator.create_valid_dcv_with_caa_check_request()
        mpic_request = MpicDcvWithCaaRequest.model_validate_json(json.dumps(request.model_dump()))
        assert mpic_request.domain_or_ip_target == request.domain_or_ip_target

    def model_validate_json__should_throw_validation_error_given_missing_domain_or_ip_target(self):
        request = ValidRequestCreator.create_valid_dcv_check_request()
        request.domain_or_ip_target = None
        with pytest.raises(pydantic.ValidationError) as validation_error:
            MpicDcvWithCaaRequest.model_validate_json(json.dumps(request.model_dump()))
        assert 'domain_or_ip_target' in str(validation_error.value)

    def model_validate_json__should_return_valid_instance_given_missing_optional_parameters(self):
        request = ValidRequestCreator.create_valid_dcv_with_caa_check_request()
        request.orchestration_parameters = None
        request.caa_check_parameters = None
        mpic_request = MpicDcvWithCaaRequest.model_validate_json(json.dumps(request.model_dump()))
        assert mpic_request.domain_or_ip_target == request.domain_or_ip_target

    def model_validate_json__should_throw_validation_error_given_missing_dcv_check_parameters(self):
        request = ValidRequestCreator.create_valid_dcv_check_request()
        request.dcv_check_parameters = None
        with pytest.raises(pydantic.ValidationError) as validation_error:
            MpicDcvWithCaaRequest.model_validate_json(json.dumps(request.model_dump()))
        assert 'dcv_check_parameters' in str(validation_error.value)

    def mpic_dcv_with_caa_request__should_have_check_type_set_to_dcv_with_caa(self):
        request = ValidRequestCreator.create_valid_dcv_with_caa_check_request()
        mpic_request = MpicDcvWithCaaRequest.model_validate_json(json.dumps(request.model_dump()))
        assert mpic_request.check_type == CheckType.DCV_WITH_CAA


if __name__ == '__main__':
    pytest.main()
    