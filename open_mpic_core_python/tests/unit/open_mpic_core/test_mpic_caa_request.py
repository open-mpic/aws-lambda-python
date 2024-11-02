import json
import pydantic
import pytest
from open_mpic_core.common_domain.enum.check_type import CheckType
from open_mpic_core.mpic_coordinator.domain.mpic_request import MpicCaaRequest

from unit.test_util.valid_mpic_request_creator import ValidMpicRequestCreator


# noinspection PyMethodMayBeStatic
class TestMpicCaaRequest:
    """
        Tests correctness of configuration for Pydantic-driven auto validation of MpicCaaRequest objects.
        """

    def model_validate_json__should_return_caa_mpic_request_given_valid_caa_json(self):
        request = ValidMpicRequestCreator.create_valid_caa_mpic_request()
        mpic_request = MpicCaaRequest.model_validate_json(json.dumps(request.model_dump()))
        assert mpic_request.domain_or_ip_target == request.domain_or_ip_target

    def model_validate_json__should_throw_validation_error_given_missing_domain_or_ip_target(self):
        request = ValidMpicRequestCreator.create_valid_caa_mpic_request()
        request.domain_or_ip_target = None
        with pytest.raises(pydantic.ValidationError) as validation_error:
            MpicCaaRequest.model_validate_json(json.dumps(request.model_dump()))
        assert 'domain_or_ip_target' in str(validation_error.value)

    def model_validate_json_should_throw_validation_error_given_invalid_certificate_type(self):
        request = ValidMpicRequestCreator.create_valid_caa_mpic_request()
        request.caa_check_parameters.certificate_type = 'invalid'
        with pytest.raises(pydantic.ValidationError) as validation_error:
            MpicCaaRequest.model_validate_json(json.dumps(request.model_dump(warnings=False)))
        assert 'certificate_type' in str(validation_error.value)
        assert 'invalid' in str(validation_error.value)

    def mpic_caa_request__should_have_check_type_set_to_caa(self):
        request = ValidMpicRequestCreator.create_valid_caa_mpic_request()
        mpic_request = MpicCaaRequest.model_validate_json(json.dumps(request.model_dump()))
        assert mpic_request.check_type == CheckType.CAA


if __name__ == '__main__':
    pytest.main()
