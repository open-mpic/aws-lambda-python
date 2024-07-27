import json

import pytest
import os

import aws_lambda_python.lambda_controller.lambda_function as lambda_function


# noinspection PyMethodMayBeStatic
class TestMpicOrchestrator:
    @staticmethod
    @pytest.fixture(scope="class")
    def set_env_variables():
        envvars = {
            "perspective_names": "rir1.region1a|rir1.region1b|rir2.region2a|rir2.region2b|rir3.region3a|rir3.region3b",
            "validator_arns": "arn:aws:acm-pca:us-east-1:123456789012:validator/rir1.region1a|arn:aws:acm-pca:us-east-1:123456789012:validator/rir1.region1b|arn:aws:acm-pca:us-east-1:123456789012:validator/rir2.region2a|arn:aws:acm-pca:us-east-1:123456789012:validator/rir2.region2b|arn:aws:acm-pca:us-east-1:123456789012:validator/rir3.region3a|arn:aws:acm-pca:us-east-1:123456789012:validator/rir3.region3b",
            "caa_arns": "arn:aws:acm-pca:us-east-1:123456789012:caa/rir1.region1a|arn:aws:acm-pca:us-east-1:123456789012:caa/rir1.region1b|arn:aws:acm-pca:us-east-1:123456789012:caa/rir2.region2a|arn:aws:acm-pca:us-east-1:123456789012:caa/rir2.region2b|arn:aws:acm-pca:us-east-1:123456789012:caa/rir3.region3a|arn:aws:acm-pca:us-east-1:123456789012:caa/rir3.region3b",
            "default_perspective_count": "3",
            "default_quorum": "2",
            "enforce_distinct_rir_regions": "1",
            "hash_secret": "test_secret"
        }
        with pytest.MonkeyPatch.context() as class_scoped_monkeypatch:
            for k, v in envvars.items():
                class_scoped_monkeypatch.setenv(k, v)
            yield class_scoped_monkeypatch  # restore the environment afterward

    @pytest.mark.parametrize("requested_perspective_count, expected_unique_rirs", [(2, 2), (3, 3), (4, 3)])
    def random_select_perspectives_considering_rir_should_select_diverse_rirs_given_list_where_some_share_same_rir(
            self, set_env_variables, requested_perspective_count, expected_unique_rirs):
        perspectives = os.getenv("perspective_names").split("|")  # same split logic as in actual calling code
        mpic_orchestrator = lambda_function.MpicOrchestrator()
        selected_perspectives = mpic_orchestrator.random_select_perspectives_considering_rir(perspectives, requested_perspective_count, "test_identifier")
        assert len(set(map(lambda p: p.split('.')[0], selected_perspectives))) == expected_unique_rirs  # expect 3 unique rirs from setup data

    def random_select_perspectives_considering_rir_should_throw_error_given_requested_count_exceeds_total_perspectives(
            self, set_env_variables):
        perspectives = os.getenv("perspective_names").split("|")
        mpic_orchestrator = lambda_function.MpicOrchestrator()
        with pytest.raises(ValueError):
            mpic_orchestrator.random_select_perspectives_considering_rir(perspectives, 10, "test_identifier")  # expect error

    def orchestrate_mpic_should_return_error_given_failed_api_version_check(self, set_env_variables):
        payload = {
            "api-version": "0.0.0",  # invalid version
            "system-params": {"identifier": "test", "perspective-count": 3},
            "caa-details": {"caa-domains": ["example.com"]}
        }
        # convert payload to json string
        payload_as_string = json.dumps(payload)

        event = {"path": "test_path", "body": payload_as_string}
        result = lambda_function.lambda_handler(event, None)
        assert result["statusCode"] == 400
        assert "api-version-mismatch" in result["body"]

    def orchestrate_mpic_should_return_error_given_perspectives_and_perspective_count_both_specified(self, set_env_variables):
        payload = {
            "api-version": "1.0.0",
            "system-params": {"identifier": "test", "perspective-count": 3, "perspectives": "test1|test2|test3"},
            "caa-details": {"caa-domains": ["example.com"]}
        }
        # convert payload to json string
        payload_as_string = json.dumps(payload)

        event = {"path": "test_path", "body": payload_as_string}
        result = lambda_function.lambda_handler(event, None)
        assert result["statusCode"] == 400
        assert "perspectives-and-perspective-count" in result["body"]

    # FIXME: This test is expected to fail because the code does not check for invalid perspective count
    @pytest.mark.xfail
    def orchestrate_mpic_should_return_error_given_invalid_perspective_count(self, set_env_variables):
        payload = {
            "api-version": "1.0.0",
            "system-params": {"identifier": "test", "perspective-count": 0},
            "caa-details": {"caa-domains": ["example.com"]}
        }
        # convert payload to json string
        payload_as_string = json.dumps(payload)

        event = {"path": "test_path", "body": payload_as_string}
        result = lambda_function.lambda_handler(event, None)
        assert result["statusCode"] == 400
        assert "invalid-perspective-count" in result["body"]

    # FIXME: This test is expected to fail because the code does not check for invalid perspective list
    @pytest.mark.xfail
    def orchestrate_mpic_should_return_error_given_invalid_perspective_list(self, set_env_variables):
        payload = {
            "api-version": "1.0.0",
            "system-params": {"identifier": "test", "perspectives": "test1|test2|test3|test4"},
            "caa-details": {"caa-domains": ["example.com"]}
        }
        # convert payload to json string
        payload_as_string = json.dumps(payload)

        event = {"path": "test_path", "body": payload_as_string}
        result = lambda_function.lambda_handler(event, None)
        assert result["statusCode"] == 400
        assert "invalid-perspectives" in result["body"]

    # FIXME: This test is expected to fail because the code does not dynamically calculate required quorum size
    @pytest.mark.xfail
    @pytest.mark.parametrize("requested_perspective_count, expected_quorum_size", [(4, 3), (5, 4), (6, 4)])
    def orchestrate_mpic_should_dynamically_set_required_quorum_count_given_no_quorum_specified(
            self, set_env_variables,requested_perspective_count, expected_quorum_size):
        payload = {
            "api-version": "1.0.0",
            "system-params": {"identifier": "test", "perspective-count": requested_perspective_count},
            "caa-details": {"caa-domains": ["example.com"]}
        }
        # convert payload to json string
        payload_as_string = json.dumps(payload)

        event = {"path": "test_path", "body": payload_as_string}
        result = lambda_function.lambda_handler(event, None)
        assert result["statusCode"] == 200
        assert "required-quorum-count" in result["body"]
        body_as_dict = json.loads(result["body"])
        actual_quorum_count = body_as_dict["required-quorum-count"]
        assert actual_quorum_count == expected_quorum_size

    # FIXME: This test is expected to fail because the code does not validate quorum count
    @pytest.mark.xfail
    def orchestrate_mpic_should_return_error_given_quorum_count_too_high(self, set_env_variables):
        payload = {
            "api-version": "1.0.0",
            "system-params": {"identifier": "test", "perspective-count": 3, "quorum": 4},
            "caa-details": {"caa-domains": ["example.com"]}
        }
        # convert payload to json string
        payload_as_string = json.dumps(payload)

        event = {"path": "test_path", "body": payload_as_string}
        result = lambda_function.lambda_handler(event, None)
        assert result["statusCode"] == 400
        assert "invalid-quorum-count" in result["body"]

    # FIXME: This test is expected to fail because the code does not validate quorum count
    @pytest.mark.xfail
    def orchestrate_mpic_should_return_error_given_quorum_count_too_low(self, set_env_variables):
        payload = {
            "api-version": "1.0.0",
            "system-params": {"identifier": "test", "perspective-count": 3, "quorum": 1},
            "caa-details": {"caa-domains": ["example.com"]}
        }
        # convert payload to json string
        payload_as_string = json.dumps(payload)

        event = {"path": "test_path", "body": payload_as_string}
        result = lambda_function.lambda_handler(event, None)
        assert result["statusCode"] == 400
        assert "invalid-quorum-count" in result["body"]

if __name__ == '__main__':
    pytest.main()
