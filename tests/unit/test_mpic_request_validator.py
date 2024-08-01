import pytest

from aws_lambda_python.mpic_coordinator.mpic_request_validator import MpicRequestValidator


# noinspection PyMethodMayBeStatic
class TestMpicRequestValidator:
    def __create_valid_caa_check_request(self):
        return {
            "api-version": "1.0.0",
            "system-params": {"identifier": "test"},
            "caa-details": {"certificate-type": "tls-server"}
        }

    def __create_valid_dcv_check_request(self):
        return {
            "api-version": "1.0.0",
            "system-params": {"identifier": "test"},
            "validation-method": "dns-generic",
            "validation-details": {"path": "test"}
        }

    def validate_request_body_should_return_true_and_empty_message_list_given_valid_caa_check_request(self):
        request_path = "/caa-check"
        body = self.__create_valid_caa_check_request()
        is_body_valid, body_validation_issues = MpicRequestValidator.validate_request_body(request_path, body)
        assert is_body_valid is True
        assert len(body_validation_issues) == 0

    def validate_request_body_should_return_true_and_empty_message_list_given_valid_dcv_check_request(self):
        request_path = "/validation"
        body = self.__create_valid_dcv_check_request()
        is_body_valid, body_validation_issues = MpicRequestValidator.validate_request_body(request_path, body)
        assert is_body_valid is True
        assert len(body_validation_issues) == 0

    def validate_request_body_should_return_false_and_message_given_missing_api_version(self):
        request_path = "/caa-check"
        body = self.__create_valid_caa_check_request()
        del body["api-version"] # remove api-version field
        is_body_valid, body_validation_issues = MpicRequestValidator.validate_request_body(request_path, body)
        assert is_body_valid is False
        assert "missing-api-version" in body_validation_issues

    def validate_request_body_should_return_false_and_message_given_missing_system_params(self):
        request_path = "/caa-check"
        body = self.__create_valid_caa_check_request()
        del body["system-params"]  # remove system-params field
        is_body_valid, body_validation_issues = MpicRequestValidator.validate_request_body(request_path, body)
        assert is_body_valid is False
        assert "missing-system-params" in body_validation_issues

    # TODO rename when you rename identifier field in the spec
    def validate_request_body_should_return_false_and_message_given_missing_identifier(self):
        request_path = "/caa-check"
        body = self.__create_valid_caa_check_request()
        del body["system-params"]["identifier"]  # remove identifier field
        is_body_valid, body_validation_issues = MpicRequestValidator.validate_request_body(request_path, body)
        assert is_body_valid is False
        assert "missing-domain-or-ip-target" in body_validation_issues

    def validate_request_body_should_return_false_and_message_given_both_perspective_and_perspective_count_present(self):
        request_path = "/caa-check"
        body = self.__create_valid_caa_check_request()
        body["system-params"]["perspectives"] = ["perspective1", "perspective2"]
        body["system-params"]["perspective-count"] = 2
        is_body_valid, body_validation_issues = MpicRequestValidator.validate_request_body(request_path, body)
        assert is_body_valid is False
        assert "contains-both-perspectives-and-perspective-count" in body_validation_issues

    def validate_request_body_should_return_false_and_message_given_invalid_certificate_type_specified(self):
        request_path = "/caa-check"
        body = self.__create_valid_caa_check_request()
        body["caa-details"]["certificate-type"] = "invalid-certificate-type"
        is_body_valid, body_validation_issues = MpicRequestValidator.validate_request_body(request_path, body)
        assert is_body_valid is False
        assert "invalid-certificate-type-in-caa-details" in body_validation_issues

    def validate_request_body_should_return_false_and_message_given_missing_validation_method_for_dcv(self):
        request_path = "/validation"
        body = self.__create_valid_dcv_check_request()
        del body["validation-method"]
        is_body_valid, body_validation_issues = MpicRequestValidator.validate_request_body(request_path, body)
        assert is_body_valid is False
        assert "missing-validation-method" in body_validation_issues

    def validate_request_body_should_return_false_and_message_given_invalid_validation_method_specified(self):
        request_path = "/validation"
        body = self.__create_valid_dcv_check_request()
        body["validation-method"] = "invalid-validation-method"
        is_body_valid, body_validation_issues = MpicRequestValidator.validate_request_body(request_path, body)
        assert is_body_valid is False
        assert "invalid-validation-method" in body_validation_issues


if __name__ == '__main__':
    pytest.main()
