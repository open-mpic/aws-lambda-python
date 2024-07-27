import json

import pytest
import os

import aws_lambda_python.lambda_controller.lambda_function as lambda_function


# noinspection PyMethodMayBeStatic
class TestMpicOrchestrator:
    @staticmethod
    @pytest.fixture(scope="class")
    def set_environment_variables():
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
            self, set_environment_variables, requested_perspective_count, expected_unique_rirs):
        perspectives = os.getenv("perspective_names").split("|")  # same split logic as in actual calling code
        selected_perspectives = lambda_function.MpicOrchestrator.random_select_perspectives_considering_rir(perspectives, requested_perspective_count)
        assert len(set(map(lambda p: p.split('.')[0], selected_perspectives))) == expected_unique_rirs  # expect 3 unique rirs from setup data

    def random_select_perspectives_considering_rir_should_throw_error_given_requested_count_exceeds_total_perspectives(
            self, set_environment_variables):
        perspectives = os.getenv("perspective_names").split("|")
        with pytest.raises(ValueError):
            lambda_function.MpicOrchestrator.random_select_perspectives_considering_rir(perspectives, 10)  # expect error

    def orchestrate_mpic_should_return_400_error_given_failed_api_version_check(self, set_environment_variables):
        payload = {
            "api-version": "0.0.0",  # invalid version
            "system-params": {
                "identifier": "test",
                "perspective-count": 3,
                "quorum-count": 2
            },
            "caa-details": {
                "caa-domains": [
                    "mozilla.com"
                ]
            }
        }
        # convert payload to json string
        payload_as_string = json.dumps(payload)

        event = {"path": "test_path", "body": payload_as_string}
        result = lambda_function.lambda_handler(event, None)
        assert result["statusCode"] == 400


if __name__ == '__main__':
    pytest.main()
