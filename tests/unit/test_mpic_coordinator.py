import json
import pytest
import os

from aws_lambda_python.mpic_coordinator.mpic_coordinator import MpicCoordinator


# noinspection PyMethodMayBeStatic
class TestMpicCoordinator:
    @staticmethod
    @pytest.fixture(scope='class')
    def set_env_variables():
        envvars = {
            'perspective_names': 'rir1.region1a|rir1.region1b|rir2.region2a|rir2.region2b|rir3.region3a|rir3.region3b',
            'validator_arns': 'arn:aws:acm-pca:us-east-1:123456789012:validator/rir1.region1a|arn:aws:acm-pca:us-east-1:123456789012:validator/rir1.region1b|arn:aws:acm-pca:us-east-1:123456789012:validator/rir2.region2a|arn:aws:acm-pca:us-east-1:123456789012:validator/rir2.region2b|arn:aws:acm-pca:us-east-1:123456789012:validator/rir3.region3a|arn:aws:acm-pca:us-east-1:123456789012:validator/rir3.region3b',
            'caa_arns': 'arn:aws:acm-pca:us-east-1:123456789012:caa/rir1.region1a|arn:aws:acm-pca:us-east-1:123456789012:caa/rir1.region1b|arn:aws:acm-pca:us-east-1:123456789012:caa/rir2.region2a|arn:aws:acm-pca:us-east-1:123456789012:caa/rir2.region2b|arn:aws:acm-pca:us-east-1:123456789012:caa/rir3.region3a|arn:aws:acm-pca:us-east-1:123456789012:caa/rir3.region3b',
            'default_perspective_count': '3',
            'default_quorum': '2',
            'enforce_distinct_rir_regions': '1',
            'hash_secret': 'test_secret',
            'caa_domains': 'example.com|example.net|example.org'
        }
        with pytest.MonkeyPatch.context() as class_scoped_monkeypatch:
            for k, v in envvars.items():
                class_scoped_monkeypatch.setenv(k, v)
            yield class_scoped_monkeypatch  # restore the environment afterward

    @pytest.mark.parametrize('requested_perspective_count, expected_unique_rirs', [(2, 2), (3, 3), (4, 3)])
    def random_select_perspectives_considering_rir__should_select_diverse_rirs_given_list_where_some_share_same_rir(
            self, set_env_variables, requested_perspective_count, expected_unique_rirs):
        perspectives = os.getenv('perspective_names').split('|')  # same split logic as in actual calling code
        mpic_coordinator = MpicCoordinator()
        selected_perspectives = mpic_coordinator.random_select_perspectives_considering_rir(perspectives, requested_perspective_count, 'test_identifier')
        assert len(set(map(lambda p: p.split('.')[0], selected_perspectives))) == expected_unique_rirs  # expect 3 unique rirs from setup data

    def random_select_perspectives_considering_rir__should_throw_error_given_requested_count_exceeds_total_perspectives(
            self, set_env_variables):
        perspectives = os.getenv('perspective_names').split('|')
        mpic_coordinator = MpicCoordinator()
        with pytest.raises(ValueError):
            mpic_coordinator.random_select_perspectives_considering_rir(perspectives, 10, 'test_identifier')  # expect error

    def coordinate_mpic__should_return_error_given_failed_api_version_check(self, set_env_variables):
        body = {
            'api-version': '0.0.0',  # invalid version
            'system-params': {'identifier': 'test', 'perspective-count': 3},
            'caa-details': {'caa-domains': ['example.com']}
        }
        event = {'path': 'test_path', 'body': json.dumps(body)}
        mpic_coordinator = MpicCoordinator()
        result = mpic_coordinator.coordinate_mpic(event)
        assert result['statusCode'] == 400
        assert 'api-version-mismatch' in result['body']

    def coordinate_mpic__should_return_error_given_perspectives_and_perspective_count_both_specified(self, set_env_variables):
        body = {
            'api-version': '1.0.0',
            'system-params': {'identifier': 'test', 'perspective-count': 3, 'perspectives': 'test1|test2|test3'}
        }
        event = {'path': 'test_path', 'body': json.dumps(body)}
        mpic_coordinator = MpicCoordinator()
        result = mpic_coordinator.coordinate_mpic(event)
        assert result['statusCode'] == 400
        assert 'perspectives-and-perspective-count' in result['body']

    # FIXME: This test is expected to fail because the code does not check for invalid perspective count
    @pytest.mark.xfail
    def coordinate_mpic__should_return_error_given_invalid_perspective_count(self, set_env_variables):
        body = {
            'api-version': '1.0.0',
            'system-params': {'identifier': 'test', 'perspective-count': 0}
        }
        event = {'path': 'test_path', 'body': json.dumps(body)}
        mpic_coordinator = MpicCoordinator()
        result = mpic_coordinator.coordinate_mpic(event)
        assert result['statusCode'] == 400
        assert 'invalid-perspective-count' in result['body']

    # FIXME: This test is expected to fail because the code does not check for invalid perspective list
    @pytest.mark.xfail
    def coordinate_mpic__should_return_error_given_invalid_perspective_list(self, set_env_variables):
        body = {
            'api-version': '1.0.0',
            'system-params': {'identifier': 'test', 'perspectives': 'test1|test2|test3|test4'}
        }
        event = {'path': 'test_path', 'body': json.dumps(body)}
        mpic_coordinator = MpicCoordinator()
        result = mpic_coordinator.coordinate_mpic(event)
        assert result['statusCode'] == 400
        assert 'invalid-perspectives' in result['body']

    # FIXME: This test is expected to fail because the code does not validate quorum count
    @pytest.mark.xfail
    @pytest.mark.parametrize('quorum_count', [4, 1])
    def coordinate_mpic__should_return_error_given_invalid_quorum_count(self, set_env_variables, quorum_count):
        body = {
            'api-version': '1.0.0',
            'system-params': {'identifier': 'test', 'perspective-count': 3, 'quorum': quorum_count}
        }
        event = {'path': 'test_path', 'body': json.dumps(body)}
        mpic_coordinator = MpicCoordinator()
        result = mpic_coordinator.coordinate_mpic(event)
        assert result['statusCode'] == 400
        assert 'invalid-quorum-count' in result['body']

    # FIXME: This test is expected to fail because the code does not dynamically calculate required quorum size
    @pytest.mark.xfail
    @pytest.mark.parametrize('requested_perspective_count, expected_quorum_size', [(4, 3), (5, 4), (6, 4)])
    def coordinate_mpic__should_dynamically_set_required_quorum_count_given_no_quorum_specified(
            self, set_env_variables, requested_perspective_count, expected_quorum_size):
        body = {
            'api-version': '1.0.0',
            'system-params': {'identifier': 'test', 'perspective-count': requested_perspective_count},
        }
        event = {'path': 'test_path', 'body': json.dumps(body)}
        mpic_coordinator = MpicCoordinator()
        result = mpic_coordinator.coordinate_mpic(event)
        assert result['statusCode'] == 200
        assert 'required-quorum-count' in result['body']
        body_as_dict = json.loads(result['body'])
        actual_quorum_count = body_as_dict['required-quorum-count']
        assert actual_quorum_count == expected_quorum_size

    # FIXME: This test is expected to fail; if identifier is missing what should happen? (ditto for all other fields)
    @pytest.mark.xfail
    def coordinate_mpic__should_return_error_given_missing_identifier(self, set_env_variables):
        body = {
            'api-version': '1.0.0',
            'system-params': {'perspective-count': 3}
        }
        event = {'path': 'test_path', 'body': json.dumps(body)}
        mpic_coordinator = MpicCoordinator()
        result = mpic_coordinator.coordinate_mpic(event)
        assert result['statusCode'] == 400
        assert 'missing-identifier' in result['body']

    def collect_async_calls_to_issue__should_have_only_caa_calls_given_caa_check_request_path(self, set_env_variables):
        body = {
            'api-version': '1.0.0',
            'system-params': {'identifier': 'test'},
            'caa-details': {'caa-domains': ['example.com']}
        }
        perspectives_to_use = os.getenv('perspective_names').split('|')
        mpic_coordinator = MpicCoordinator()
        call_list = mpic_coordinator.collect_async_calls_to_issue('/caa-check', body, perspectives_to_use)
        assert len(call_list) == 6
        # ensure each call is of type 'caa' (first element in call tuple)
        assert set(map(lambda result: result[0], call_list)) == {'caa'}

    def collect_async_calls_to_issue__should_have_only_validator_calls_given_validation_request_path(self, set_env_variables):
        body = {
            'api-version': '1.0.0',
            'system-params': {'identifier': 'test'},
            'validation-method': 'test-method',
            'validation-details': 'test-details'
        }
        perspectives_to_use = os.getenv('perspective_names').split('|')
        mpic_coordinator = MpicCoordinator()
        call_list = mpic_coordinator.collect_async_calls_to_issue('/validation', body, perspectives_to_use)
        assert len(call_list) == 6
        # ensure each call is of type 'validation' (first element in call tuple)
        assert set(map(lambda result: result[0], call_list)) == {'validation'}

    @pytest.mark.xfail  # FIXME: This test is expected to fail; there is no way to easily inspect caa domains used
    def collect_async_calls_to_issue__should_use_default_caa_domains_if_none_specified(self, set_env_variables):
        body = {
            'api-version': '1.0.0',
            'system-params': {'identifier': 'test'}
        }
        perspectives_to_use = os.getenv('perspective_names').split('|')
        mpic_coordinator = MpicCoordinator()
        mpic_coordinator.collect_async_calls_to_issue('/caa-check', body, perspectives_to_use)
        # ensure each call has the default caa domains
        assert False


if __name__ == '__main__':
    pytest.main()
