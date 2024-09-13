import io
import json
import pytest
import os
import importlib.resources as pkg_resources

import yaml
from pydantic import TypeAdapter

from aws_lambda_python.common_domain.check_response import CaaCheckResponse, CaaCheckResponseDetails
from aws_lambda_python.common_domain.enum.dcv_validation_method import DcvValidationMethod
from aws_lambda_python.common_domain.enum.check_type import CheckType
from aws_lambda_python.common_domain.messages.ErrorMessages import ErrorMessages
from aws_lambda_python.mpic_coordinator.domain.enum.request_path import RequestPath
from aws_lambda_python.mpic_coordinator.messages.mpic_request_validation_messages import MpicRequestValidationMessages
from aws_lambda_python.mpic_coordinator.mpic_coordinator import MpicCoordinator
from botocore.response import StreamingBody

from valid_request_creator import ValidRequestCreator
from aws_lambda_python.mpic_coordinator.domain.mpic_response import MpicResponse, AnnotatedMpicResponse


# noinspection PyMethodMayBeStatic
class TestMpicCoordinator:
    @classmethod
    def setup_class(cls):
        cls.mpic_response_adapter: TypeAdapter[MpicResponse] = TypeAdapter(AnnotatedMpicResponse)

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

    def coordinate_mpic__should_return_error_given_invalid_request_body(self, set_env_variables):
        request = ValidRequestCreator.create_valid_dcv_check_request()
        request.domain_or_ip_target = None
        event = {'path': RequestPath.MPIC, 'body': request.model_dump()}
        mpic_coordinator = MpicCoordinator()
        result = mpic_coordinator.coordinate_mpic(event)
        # FIXME need to capture pydantic validation error and put it into response (for now... FastAPI may render that unnecessary)
        assert result['statusCode'] == 400
        response_body = json.loads(result['body'])
        assert response_body['error'] == MpicRequestValidationMessages.REQUEST_VALIDATION_FAILED.key

    def coordinate_mpic__should_return_error_given_invalid_check_type(self, set_env_variables):
        request = ValidRequestCreator.create_valid_dcv_check_request()
        request.check_type = 'invalid_check_type'
        event = {'path': RequestPath.MPIC, 'body': request.model_dump()}
        mpic_coordinator = MpicCoordinator()
        result = mpic_coordinator.coordinate_mpic(event)
        assert result['statusCode'] == 400
        response_body = json.loads(result['body'])
        assert response_body['error'] == MpicRequestValidationMessages.REQUEST_VALIDATION_FAILED.key

    def coordinate_mpic__should_return_error_given_invalid_request_path(self, set_env_variables):
        request = ValidRequestCreator.create_valid_dcv_check_request()
        event = {'path': 'invalid_path', 'body': request.model_dump()}
        mpic_coordinator = MpicCoordinator()
        result = mpic_coordinator.coordinate_mpic(event)
        assert result['statusCode'] == 400
        response_body = json.loads(result['body'])
        assert response_body['error'] == MpicRequestValidationMessages.REQUEST_VALIDATION_FAILED.key
        assert response_body['validation_issues'][0] == MpicRequestValidationMessages.UNSUPPORTED_REQUEST_PATH.key

    @pytest.mark.parametrize('requested_perspective_count, expected_quorum_size', [(4, 3), (5, 4), (6, 4)])
    def determine_required_quorum_count__should_dynamically_set_required_quorum_count_given_no_quorum_specified(
            self, set_env_variables, requested_perspective_count, expected_quorum_size):
        command = ValidRequestCreator.create_valid_caa_check_request()
        command.orchestration_parameters.quorum_count = None
        mpic_coordinator = MpicCoordinator()
        required_quorum_count = mpic_coordinator.determine_required_quorum_count(command.orchestration_parameters, requested_perspective_count)
        assert required_quorum_count == expected_quorum_size

    def determine_required_quorum_count__should_use_specified_quorum_count_given_quorum_specified(self, set_env_variables):
        command = ValidRequestCreator.create_valid_caa_check_request()
        command.orchestration_parameters.quorum_count = 5
        mpic_coordinator = MpicCoordinator()
        required_quorum_count = mpic_coordinator.determine_required_quorum_count(command.orchestration_parameters, 6)
        assert required_quorum_count == 5

    def collect_async_calls_to_issue__should_have_only_caa_calls_given_caa_check_type(self, set_env_variables):
        request = ValidRequestCreator.create_valid_caa_check_request()
        perspectives_to_use = os.getenv('perspective_names').split('|')
        mpic_coordinator = MpicCoordinator()
        call_list = mpic_coordinator.collect_async_calls_to_issue(request, perspectives_to_use)
        assert len(call_list) == 6
        assert set(map(lambda call_result: call_result.check_type, call_list)) == {CheckType.CAA}  # ensure each call is of type 'caa'

    def collect_async_calls_to_issue__should_include_caa_check_parameters_as_caa_params_in_input_args_if_present(self, set_env_variables):
        request = ValidRequestCreator.create_valid_caa_check_request()
        request.caa_check_parameters.caa_domains = ['example.com']
        perspectives_to_use = os.getenv('perspective_names').split('|')
        mpic_coordinator = MpicCoordinator()
        call_list = mpic_coordinator.collect_async_calls_to_issue(request, perspectives_to_use)
        assert all(call.input_args.caa_check_parameters.caa_domains == ['example.com'] for call in call_list)

    def collect_async_calls_to_issue__should_have_only_dcv_calls_and_include_validation_input_args_given_dcv_check_type(self, set_env_variables):
        request = ValidRequestCreator.create_valid_dcv_check_request(DcvValidationMethod.DNS_GENERIC)
        perspectives_to_use = os.getenv('perspective_names').split('|')
        mpic_coordinator = MpicCoordinator()
        call_list = mpic_coordinator.collect_async_calls_to_issue(request, perspectives_to_use)
        assert len(call_list) == 6
        assert set(map(lambda call_result: call_result.check_type, call_list)) == {CheckType.DCV}  # ensure each call is of type 'dcv'
        assert all(call.input_args.dcv_check_parameters.validation_method == DcvValidationMethod.DNS_GENERIC for call in call_list)
        assert all(call.input_args.dcv_check_parameters.validation_details.dns_name_prefix == 'test' for call in call_list)

    def collect_async_calls_to_issue__should_have_caa_and_dcv_calls_given_dcv_with_caa_check_type(self, set_env_variables):
        request = ValidRequestCreator.create_valid_dcv_with_caa_check_request()
        perspectives_to_use = os.getenv('perspective_names').split('|')
        mpic_coordinator = MpicCoordinator()
        call_list = mpic_coordinator.collect_async_calls_to_issue(request, perspectives_to_use)
        assert len(call_list) == 12
        # ensure the list contains both 'caa' and 'dcv' calls
        assert set(map(lambda call_result: call_result.check_type, call_list)) == {CheckType.CAA, CheckType.DCV}

    def coordinate_mpic__should_return_200_and_results_given_successful_caa_corroboration(self, set_env_variables, mocker):
        request = ValidRequestCreator.create_valid_caa_check_request()
        event = {'path': RequestPath.MPIC, 'body': json.dumps(request.model_dump())}
        mocker.patch('aws_lambda_python.mpic_coordinator.mpic_coordinator.MpicCoordinator.thread_call',
                     side_effect=self.create_payload_with_streaming_body)
        mpic_coordinator = MpicCoordinator()
        result = mpic_coordinator.coordinate_mpic(event)
        assert result['statusCode'] == 200
        mpic_response = self.mpic_response_adapter.validate_json(result['body'])
        assert mpic_response.is_valid is True

    def coordinate_mpic__should_successfully_carry_out_caa_mpic_given_no_parameters_besides_target(self, set_env_variables, mocker):
        request = ValidRequestCreator.create_valid_caa_check_request()
        request.orchestration_parameters = None
        request.caa_check_parameters = None
        event = {'path': RequestPath.MPIC, 'body': json.dumps(request.model_dump())}
        mocker.patch('aws_lambda_python.mpic_coordinator.mpic_coordinator.MpicCoordinator.thread_call',
                     side_effect=self.create_payload_with_streaming_body)
        mpic_coordinator = MpicCoordinator()
        result = mpic_coordinator.coordinate_mpic(event)
        assert result['statusCode'] == 200
        mpic_response = self.mpic_response_adapter.validate_json(result['body'])
        assert mpic_response.is_valid is True

    @pytest.mark.parametrize('check_type', [CheckType.CAA, CheckType.DCV])
    def coordinate_mpic__should_return_check_failure_message_given_remote_perspective_failure(self, set_env_variables, check_type, mocker):
        request = None
        match check_type:
            case CheckType.CAA:
                request = ValidRequestCreator.create_valid_caa_check_request()
            case CheckType.DCV:
                request = ValidRequestCreator.create_valid_dcv_check_request()
        event = {'path': RequestPath.MPIC, 'body': json.dumps(request.model_dump())}
        mocker.patch('aws_lambda_python.mpic_coordinator.mpic_coordinator.MpicCoordinator.thread_call',
                     side_effect=self.create_payload_with_streaming_body_with_failure)
        mpic_coordinator = MpicCoordinator()
        result = mpic_coordinator.coordinate_mpic(event)
        assert result['statusCode'] == 200
        mpic_response = self.mpic_response_adapter.validate_json(result['body'])
        assert mpic_response.is_valid is False
        for perspective in mpic_response.perspectives:
            assert perspective.check_passed is False
            assert perspective.errors[0].error_type == ErrorMessages.COORDINATOR_COMMUNICATION_ERROR.key

    def load_aws_region_config__should_return_dict_of_aws_regions_with_proximity_info_by_region_code(self, set_env_variables):
        aws_regions_yaml = yaml.safe_load(pkg_resources.open_text('resources', 'aws_region_config.yaml'))
        loaded_aws_regions = MpicCoordinator.load_aws_region_config()
        assert len(loaded_aws_regions.keys()) == len(aws_regions_yaml['aws_available_regions'])
        # for example, us-east-1 is too close to us-east-2
        assert 'us-east-2' in loaded_aws_regions['us-east-1'].too_close_region_codes
        assert 'us-east-1' in loaded_aws_regions['us-east-2'].too_close_region_codes

    # noinspection PyUnusedLocal
    def create_payload_with_streaming_body(self, call_config):
        # note: all perspective response details will be identical in these tests due to this mocking
        expected_response_body = CaaCheckResponse(perspective='us-east-4', check_passed=True,
                                                  details=CaaCheckResponseDetails(caa_record_present=False))
        expected_response = {'statusCode': 200, 'body': json.dumps(expected_response_body.model_dump())}
        json_bytes = json.dumps(expected_response).encode('utf-8')
        file_like_response = io.BytesIO(json_bytes)
        streaming_body_response = StreamingBody(file_like_response, len(json_bytes))
        return {'Payload': streaming_body_response}

    # noinspection PyUnusedLocal
    def create_payload_with_streaming_body_with_failure(self, call_config):
        # note: all perspective response details will be identical in these tests due to this mocking
        expected_response_body = 'Something went wrong'
        expected_response = {'statusCode': 500, 'body': expected_response_body}
        json_bytes = json.dumps(expected_response).encode('utf-8')
        file_like_response = io.BytesIO(json_bytes)
        streaming_body_response = StreamingBody(file_like_response, len(json_bytes))
        return {'Payload': streaming_body_response}

if __name__ == '__main__':
    pytest.main()
