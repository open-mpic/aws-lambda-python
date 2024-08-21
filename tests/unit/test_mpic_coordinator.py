import json
import pytest
import os

from aws_lambda_python.mpic_coordinator.config.service_config import API_VERSION
from aws_lambda_python.mpic_coordinator.domain.check_type import CheckType
from aws_lambda_python.mpic_coordinator.domain.request_path import RequestPath
from aws_lambda_python.mpic_coordinator.messages.validation_messages import ValidationMessages
from aws_lambda_python.mpic_coordinator.mpic_coordinator import MpicCoordinator
from valid_request_creator import ValidRequestCreator


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
            'enforce_distinct_rir_regions': '1',  # TODO may not need this...
            'hash_secret': 'test_secret',
            'caa_domains': 'example.com|example.net|example.org'
        }
        with pytest.MonkeyPatch.context() as class_scoped_monkeypatch:
            for k, v in envvars.items():
                class_scoped_monkeypatch.setenv(k, v)
            yield class_scoped_monkeypatch  # restore the environment afterward

    # TODO discuss BR requirement of 2+ RIRs. If 2+ cannot be selected, is that an error state (500 code)?
    # TODO discuss BR requirement of 500k+ regional distance. This is not currently implemented.
    @pytest.mark.parametrize('requested_perspective_count, expected_unique_rirs', [(2, 2), (3, 3), (4, 3)])
    def select_random_perspectives_across_rirs__should_select_diverse_rirs_given_list_where_some_share_same_rir(
            self, set_env_variables, requested_perspective_count, expected_unique_rirs):
        perspectives = os.getenv('perspective_names').split('|')  # same split logic as in actual calling code
        mpic_coordinator = MpicCoordinator()
        selected_perspectives = mpic_coordinator.select_random_perspectives_across_rirs(perspectives, requested_perspective_count, 'test_target')
        assert len(set(map(lambda p: p.split('.')[0], selected_perspectives))) == expected_unique_rirs  # expect 3 unique rirs from setup data

    def select_random_perspectives_across_rirs__should_throw_error_given_requested_count_exceeds_total_perspectives(
            self, set_env_variables):
        perspectives = os.getenv('perspective_names').split('|')
        excessive_count = len(perspectives) + 1
        mpic_coordinator = MpicCoordinator()
        with pytest.raises(ValueError):
            mpic_coordinator.select_random_perspectives_across_rirs(perspectives, excessive_count, 'test_target')  # expect error

    @pytest.mark.parametrize('field_to_delete', ['api_version', 'system_params'])
    def coordinate_mpic__should_return_error_given_invalid_request_body(self, set_env_variables, field_to_delete):
        # request = ValidRequestCreator.create_valid_dcv_with_caa_check_request()
        # remove from request body the field that should be missing
        # request.__setattr__(field_to_delete, None)
        body = ValidRequestCreator.create_valid_caa_check_request_body()
        del body[field_to_delete]
        event = {'path': RequestPath.CAA_CHECK, 'body': json.dumps(body)}
        mpic_coordinator = MpicCoordinator()
        result = mpic_coordinator.coordinate_mpic(event)
        # FIXME need to capture pydantic validation error and put it into response (for now... FastAPI may render that unnecessary)
        assert result['statusCode'] == 400
        response_body = json.loads(result['body'])
        assert response_body['error'] == ValidationMessages.REQUEST_VALIDATION_FAILED.key
        assert field_to_delete in str(response_body['validation-issues'][0])

    @pytest.mark.parametrize('requested_perspective_count, expected_quorum_size', [(4, 3), (5, 4), (6, 4)])
    def determine_required_quorum_count__should_dynamically_set_required_quorum_count_given_no_quorum_specified(
            self, set_env_variables, requested_perspective_count, expected_quorum_size):
        command = ValidRequestCreator.create_valid_caa_check_request()
        command.system_params.quorum_count = None
        mpic_coordinator = MpicCoordinator()
        required_quorum_count = mpic_coordinator.determine_required_quorum_count(command.system_params, requested_perspective_count)
        assert required_quorum_count == expected_quorum_size

    def determine_required_quorum_count__should_use_specified_quorum_count_given_quorum_specified(self, set_env_variables):
        command = ValidRequestCreator.create_valid_caa_check_request()
        command.system_params.quorum_count = 5
        mpic_coordinator = MpicCoordinator()
        required_quorum_count = mpic_coordinator.determine_required_quorum_count(command.system_params, 6)
        assert required_quorum_count == 5

    def collect_async_calls_to_issue__should_have_only_caa_calls_given_caa_check_request_path(self, set_env_variables):
        body = {
            'api-version': API_VERSION,
            'system-params': {'domain-or-ip-target': 'test'}
        }
        perspectives_to_use = os.getenv('perspective_names').split('|')
        mpic_coordinator = MpicCoordinator()
        call_list = mpic_coordinator.collect_async_calls_to_issue(RequestPath.CAA_CHECK, body, perspectives_to_use)
        assert len(call_list) == 6
        assert set(map(lambda call_result: call_result.check_type, call_list)) == {CheckType.CAA}  # ensure each call is of type 'caa'

    def collect_async_calls_to_issue__should_include_caa_details_as_caa_params_in_input_args_if_present(self, set_env_variables):
        body = {
            'api-version': API_VERSION,
            'system-params': {'domain-or-ip-target': 'test'},
            'caa-details': {'caa-domains': ['example.com']}
        }
        perspectives_to_use = os.getenv('perspective_names').split('|')
        mpic_coordinator = MpicCoordinator()
        call_list = mpic_coordinator.collect_async_calls_to_issue(RequestPath.CAA_CHECK, body, perspectives_to_use)
        assert all(call.input_args['caa-params']['caa-domains'] == ['example.com'] for call in call_list)

    def collect_async_calls_to_issue__should_have_only_dcv_calls_and_include_validation_input_args_given_dcv_request_path(self, set_env_variables):
        body = {
            'api-version': API_VERSION,
            'system-params': {'domain-or-ip-target': 'test'},
            'validation-method': 'test-method',
            'validation-details': 'test-details'
        }
        perspectives_to_use = os.getenv('perspective_names').split('|')
        mpic_coordinator = MpicCoordinator()
        call_list = mpic_coordinator.collect_async_calls_to_issue(RequestPath.DCV_CHECK, body, perspectives_to_use)
        assert len(call_list) == 6
        assert set(map(lambda call_result: call_result.check_type, call_list)) == {CheckType.DCV}  # ensure each call is of type 'dcv'
        assert all(call.input_args['validation-method'] == 'test-method' for call in call_list)
        assert all(call.input_args['validation-params'] == 'test-details' for call in call_list)

    def collect_async_calls_to_issue__should_have_caa_and_dcv_calls_given_dcv_with_caa_request_path(self, set_env_variables):
        body = {
            'api-version': API_VERSION,
            'system-params': {'domain-or-ip-target': 'test'},
            'caa-details': {'caa-domains': ['example.com']},
            'validation-method': 'test-method',
            'validation-details': 'test-details'
        }
        perspectives_to_use = os.getenv('perspective_names').split('|')
        mpic_coordinator = MpicCoordinator()
        call_list = mpic_coordinator.collect_async_calls_to_issue(RequestPath.DCV_WITH_CAA_CHECK, body, perspectives_to_use)
        assert len(call_list) == 12
        # ensure the list contains both 'caa' and 'dcv' calls
        assert set(map(lambda call_result: call_result.check_type, call_list)) == {CheckType.CAA, CheckType.DCV}

    @pytest.mark.skip  # FIXME: this test isn't ready; there is no way to easily inspect caa domains used
    def collect_async_calls_to_issue__should_use_default_caa_domains_if_none_specified(self, set_env_variables):
        body = {
            'api-version': API_VERSION,
            'system-params': {'domain-or-ip-target': 'test'}
        }
        perspectives_to_use = os.getenv('perspective_names').split('|')
        mpic_coordinator = MpicCoordinator()
        mpic_coordinator.collect_async_calls_to_issue(RequestPath.CAA_CHECK, body, perspectives_to_use)
        # ensure each call has the default caa domains
        assert False


if __name__ == '__main__':
    pytest.main()
