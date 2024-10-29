import io
import json
from itertools import cycle

import pytest
import os

from pydantic import TypeAdapter

from aws_lambda_python.common_domain.check_request import DcvCheckRequest
from aws_lambda_python.common_domain.check_response import CaaCheckResponse, CaaCheckResponseDetails, DcvCheckResponse, \
    DcvCheckResponseDetails
from aws_lambda_python.common_domain.enum.dcv_validation_method import DcvValidationMethod
from aws_lambda_python.common_domain.enum.check_type import CheckType
from aws_lambda_python.common_domain.messages.ErrorMessages import ErrorMessages
from aws_lambda_python.mpic_coordinator.domain.enum.request_path import RequestPath
from aws_lambda_python.mpic_coordinator.domain.mpic_orchestration_parameters import MpicRequestOrchestrationParameters
from aws_lambda_python.mpic_coordinator.domain.remote_check_call_configuration import RemoteCheckCallConfiguration
from aws_lambda_python.common_domain.remote_perspective import RemotePerspective
from aws_lambda_python.mpic_coordinator.messages.mpic_request_validation_messages import MpicRequestValidationMessages
from aws_lambda_python.mpic_coordinator.mpic_coordinator import MpicCoordinator, MpicCoordinatorConfiguration
from botocore.response import StreamingBody

from valid_request_creator import ValidRequestCreator
from aws_lambda_python.mpic_coordinator.domain.mpic_response import MpicResponse, AnnotatedMpicResponse, MpicCaaResponse


# noinspection PyMethodMayBeStatic
class TestMpicCoordinator:
    @classmethod
    def setup_class(cls):
        cls.mpic_response_adapter: TypeAdapter[MpicResponse] = TypeAdapter(AnnotatedMpicResponse)

    @staticmethod
    @pytest.fixture(scope='class')
    def set_env_variables():
        envvars = {
            'perspective_names': 'arin.us-east-1|arin.us-west-1|ripe.eu-west-2|ripe.eu-central-2|apnic.ap-northeast-1|apnic.ap-south-2',
            'validator_arns': 'arn:aws:acm-pca:us-east-1:123456789012:validator/arin.us-east-1|arn:aws:acm-pca:us-west-1:123456789012:validator/arin.us-west-1|arn:aws:acm-pca:eu-west-2:123456789012:validator/ripe.eu-west-2|arn:aws:acm-pca:eu-central-2:123456789012:validator/ripe.eu-central-2|arn:aws:acm-pca:ap-northeast-1:123456789012:validator/apnic.ap-northeast-1|arn:aws:acm-pca:ap-south-2:123456789012:validator/apnic.ap-south-2',
            'caa_arns': 'arn:aws:acm-pca:us-east-1:123456789012:caa/arin.us-east-1|arn:aws:acm-pca:us-west-1:123456789012:caa/arin.us-west-1|arn:aws:acm-pca:eu-west-2:123456789012:caa/ripe.eu-west-2|arn:aws:acm-pca:eu-central-2:123456789012:caa/ripe.eu-central-2|arn:aws:acm-pca:ap-northeast-1:123456789012:caa/apnic.ap-northeast-1|arn:aws:acm-pca:ap-south-2:123456789012:caa/apnic.ap-south-2',
            'default_perspective_count': '3',
            'enforce_distinct_rir_regions': '1',  # TODO may not need this...
            'hash_secret': 'test_secret',
            'caa_domains': 'example.com|example.net|example.org'
        }
        with pytest.MonkeyPatch.context() as class_scoped_monkeypatch:
            for k, v in envvars.items():
                class_scoped_monkeypatch.setenv(k, v)
            yield class_scoped_monkeypatch  # restore the environment afterward

    def create_cohorts_of_randomly_selected_perspectives__should_throw_error_given_requested_count_exceeds_total_perspectives(
            self, set_env_variables):
        perspectives = os.getenv('perspective_names').split('|')
        excessive_count = len(perspectives) + 1
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_successful_lambda_response, mpic_coordinator_config)
        with pytest.raises(ValueError):
            mpic_coordinator.create_cohorts_of_randomly_selected_perspectives(perspectives, excessive_count, 'test_target')  # expect error

    def create_cohorts_of_randomly_selected_perspectives__should_return_list_of_cohorts_of_requested_size(self, set_env_variables):
        perspectives = os.getenv('perspective_names').split('|')
        cohort_size = len(perspectives) // 2
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_successful_lambda_response, mpic_coordinator_config)
        cohorts = mpic_coordinator.create_cohorts_of_randomly_selected_perspectives(perspectives, cohort_size, 'test_target')
        assert len(cohorts) == 2

    def coordinate_mpic__should_return_error_given_invalid_request_body(self, set_env_variables):
        request = ValidRequestCreator.create_valid_dcv_mpic_request()
        request.domain_or_ip_target = None
        event = {'path': RequestPath.MPIC, 'body': request.model_dump()}
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_successful_lambda_response, mpic_coordinator_config)
        result = mpic_coordinator.coordinate_mpic(event['body'])
        # FIXME need to capture pydantic validation error and put it into response (for now... FastAPI may render that unnecessary)
        assert result['statusCode'] == 400
        response_body = json.loads(result['body'])
        assert response_body['error'] == MpicRequestValidationMessages.REQUEST_VALIDATION_FAILED.key

    def coordinate_mpic__should_return_error_given_invalid_check_type(self, set_env_variables):
        request = ValidRequestCreator.create_valid_dcv_mpic_request()
        request.check_type = 'invalid_check_type'
        event = {'path': RequestPath.MPIC, 'body': request.model_dump()}
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_successful_lambda_response, mpic_coordinator_config)
        result = mpic_coordinator.coordinate_mpic(event['body'])
        assert result['statusCode'] == 400
        response_body = json.loads(result['body'])
        assert response_body['error'] == MpicRequestValidationMessages.REQUEST_VALIDATION_FAILED.key

    @pytest.mark.skip(reason="Request path checking is no longer part of mpic coordinater")
    def coordinate_mpic__should_return_error_given_invalid_request_path(self, set_env_variables):
        request = ValidRequestCreator.create_valid_dcv_mpic_request()
        event = {'path': 'invalid_path', 'body': request.model_dump()}
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_successful_lambda_response, mpic_coordinator_config)
        result = mpic_coordinator.coordinate_mpic(event['body'])
        assert result['statusCode'] == 400
        response_body = json.loads(result['body'])
        assert response_body['error'] == MpicRequestValidationMessages.REQUEST_VALIDATION_FAILED.key
        assert response_body['validation_issues'][0] == MpicRequestValidationMessages.UNSUPPORTED_REQUEST_PATH.key

    @pytest.mark.parametrize('requested_perspective_count, expected_quorum_size', [(4, 3), (5, 4), (6, 4)])
    def determine_required_quorum_count__should_dynamically_set_required_quorum_count_given_no_quorum_specified(
            self, set_env_variables, requested_perspective_count, expected_quorum_size):
        command = ValidRequestCreator.create_valid_caa_mpic_request()
        command.orchestration_parameters.quorum_count = None
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_successful_lambda_response, mpic_coordinator_config)
        required_quorum_count = mpic_coordinator.determine_required_quorum_count(command.orchestration_parameters, requested_perspective_count)
        assert required_quorum_count == expected_quorum_size

    def determine_required_quorum_count__should_use_specified_quorum_count_given_quorum_specified(self, set_env_variables):
        command = ValidRequestCreator.create_valid_caa_mpic_request()
        command.orchestration_parameters.quorum_count = 5
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_successful_lambda_response, mpic_coordinator_config)
        required_quorum_count = mpic_coordinator.determine_required_quorum_count(command.orchestration_parameters, 6)
        assert required_quorum_count == 5

    def collect_async_calls_to_issue__should_have_only_caa_calls_given_caa_check_type(self, set_env_variables):
        request = ValidRequestCreator.create_valid_caa_mpic_request()
        perspective_names = os.getenv('perspective_names').split('|')
        perspectives_to_use = [RemotePerspective.from_rir_code(perspective) for perspective in perspective_names]
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_successful_lambda_response, mpic_coordinator_config)
        call_list = mpic_coordinator.collect_async_calls_to_issue(request, perspectives_to_use)
        assert len(call_list) == 6
        assert set(map(lambda call_result: call_result.check_type, call_list)) == {CheckType.CAA}  # ensure each call is of type 'caa'

    def collect_async_calls_to_issue__should_include_caa_check_parameters_as_caa_params_in_input_args_if_present(self, set_env_variables):
        request = ValidRequestCreator.create_valid_caa_mpic_request()
        request.caa_check_parameters.caa_domains = ['example.com']
        perspective_names = os.getenv('perspective_names').split('|')
        perspectives_to_use = [RemotePerspective.from_rir_code(perspective) for perspective in perspective_names]
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_successful_lambda_response, mpic_coordinator_config)
        call_list = mpic_coordinator.collect_async_calls_to_issue(request, perspectives_to_use)
        assert all(call.check_request.caa_check_parameters.caa_domains == ['example.com'] for call in call_list)

    def collect_async_calls_to_issue__should_have_only_dcv_calls_and_include_validation_input_args_given_dcv_check_type(self, set_env_variables):
        request = ValidRequestCreator.create_valid_dcv_mpic_request(DcvValidationMethod.DNS_GENERIC)
        perspective_names = os.getenv('perspective_names').split('|')
        perspectives_to_use = [RemotePerspective.from_rir_code(perspective) for perspective in perspective_names]
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_successful_lambda_response, mpic_coordinator_config)
        call_list = mpic_coordinator.collect_async_calls_to_issue(request, perspectives_to_use)
        assert len(call_list) == 6
        assert set(map(lambda call_result: call_result.check_type, call_list)) == {CheckType.DCV}  # ensure each call is of type 'dcv'
        assert all(call.check_request.dcv_check_parameters.validation_method == DcvValidationMethod.DNS_GENERIC for call in call_list)
        assert all(call.check_request.dcv_check_parameters.validation_details.dns_name_prefix == 'test' for call in call_list)

    def collect_async_calls_to_issue__should_have_caa_and_dcv_calls_given_dcv_with_caa_check_type(self, set_env_variables):
        request = ValidRequestCreator.create_valid_dcv_with_caa_mpic_request()
        perspective_names = os.getenv('perspective_names').split('|')
        perspectives_to_use = [RemotePerspective.from_rir_code(perspective) for perspective in perspective_names]
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_successful_lambda_response, mpic_coordinator_config)
        call_list = mpic_coordinator.collect_async_calls_to_issue(request, perspectives_to_use)
        assert len(call_list) == 12
        # ensure the list contains both 'caa' and 'dcv' calls
        assert set(map(lambda call_result: call_result.check_type, call_list)) == {CheckType.CAA, CheckType.DCV}

    def coordinate_mpic__should_return_200_and_results_given_successful_caa_corroboration(self, set_env_variables, mocker):
        request = ValidRequestCreator.create_valid_caa_mpic_request()
        event = {'path': RequestPath.MPIC, 'body': json.dumps(request.model_dump())}
        #mocker.patch('aws_lambda_python.mpic_coordinator.mpic_coordinator.MpicCoordinator.thread_call',
        #             side_effect=self.create_successful_lambda_response)
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_successful_lambda_response, mpic_coordinator_config)
        result = mpic_coordinator.coordinate_mpic(event['body'])
        assert result['statusCode'] == 200
        mpic_response = self.mpic_response_adapter.validate_json(result['body'])
        assert mpic_response.is_valid is True

    def coordinate_mpic__should_successfully_carry_out_caa_mpic_given_no_parameters_besides_target(self, set_env_variables, mocker):
        request = ValidRequestCreator.create_valid_caa_mpic_request()
        request.orchestration_parameters = None
        request.caa_check_parameters = None
        event = {'path': RequestPath.MPIC, 'body': json.dumps(request.model_dump())}
        #mocker.patch('aws_lambda_python.mpic_coordinator.mpic_coordinator.MpicCoordinator.thread_call',
        #             side_effect=self.create_successful_lambda_response)
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_successful_lambda_response, mpic_coordinator_config)
        result = mpic_coordinator.coordinate_mpic(event['body'])
        assert result['statusCode'] == 200
        mpic_response = self.mpic_response_adapter.validate_json(result['body'])
        assert mpic_response.is_valid is True

    def coordinate_mpic__should_successfully_carry_out_caa_mpic_given_empty_orchestration_parameters(self, set_env_variables, mocker):
        request = ValidRequestCreator.create_valid_caa_mpic_request()
        request.orchestration_parameters = MpicRequestOrchestrationParameters()
        request.caa_check_parameters = None
        print(f"serialized body object: {json.dumps(request.model_dump(exclude_none=True))}")
        event = {'path': RequestPath.MPIC, 'body': json.dumps(request.model_dump(exclude_none=True))}
        #mocker.patch('aws_lambda_python.mpic_coordinator.mpic_coordinator.MpicCoordinator.thread_call',
        #             side_effect=self.create_successful_lambda_response)
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_successful_lambda_response, mpic_coordinator_config)
        result = mpic_coordinator.coordinate_mpic(event['body'])
        assert result['statusCode'] == 200
        mpic_response = self.mpic_response_adapter.validate_json(result['body'])
        assert mpic_response.is_valid is True

    def coordinate_mpic__should_successfully_carry_out_caa_mpic_given_only_max_attempts_orchestration_parameters(self, set_env_variables, mocker):
        request = ValidRequestCreator.create_valid_caa_mpic_request()
        # Reset all fields in orchestration parameters to None
        request.orchestration_parameters = MpicRequestOrchestrationParameters()
        # Set max_attempts
        request.orchestration_parameters.max_attempts = 2
        request.caa_check_parameters = None
        print(f"serialized body object: {json.dumps(request.model_dump(exclude_none=True))}")
        event = {'path': RequestPath.MPIC, 'body': json.dumps(request.model_dump(exclude_none=True))}
        #mocker.patch('aws_lambda_python.mpic_coordinator.mpic_coordinator.MpicCoordinator.thread_call',
        #             side_effect=self.create_successful_lambda_response)
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_successful_lambda_response, mpic_coordinator_config)
        result = mpic_coordinator.coordinate_mpic(event['body'])
        assert result['statusCode'] == 200
        mpic_response = self.mpic_response_adapter.validate_json(result['body'])
        assert mpic_response.is_valid is True


    def coordinate_mpic__should_retry_corroboration_max_attempts_times_if_corroboration_fails(self, set_env_variables, mocker):
        request = ValidRequestCreator.create_valid_caa_mpic_request()
        # there are 3 rirs of 2 perspectives each in the test setup; expect 3 cohorts of 2 perspectives each
        request.orchestration_parameters = MpicRequestOrchestrationParameters(quorum_count=1, perspective_count=2, max_attempts=3)
        event = {'path': RequestPath.MPIC, 'body': json.dumps(request.model_dump())}
        # create mocks that will fail the first two attempts and succeed for the third
        #mocker.patch('aws_lambda_python.mpic_coordinator.mpic_coordinator.MpicCoordinator.thread_call',
        #             side_effect=TestMpicCoordinator.SideEffectForMockedPayloads(
        #                 self.create_failing_lambda_response, self.create_failing_lambda_response,
        #                 self.create_error_lambda_response, self.create_error_lambda_response,
        #                 self.create_successful_lambda_response
        #             ))
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_successful_lambda_response_after_n_failures_closure(4), mpic_coordinator_config)
        result = mpic_coordinator.coordinate_mpic(event['body'])
        
        assert result['statusCode'] == 200
        mpic_response: MpicCaaResponse = self.mpic_response_adapter.validate_json(result['body'])
        assert mpic_response.is_valid is True
        assert mpic_response.actual_orchestration_parameters.attempt_count == 3

    def coordinate_mpic__should_return_check_failure_if_max_attempts_were_reached_without_successful_check(self, set_env_variables, mocker):
        request = ValidRequestCreator.create_valid_caa_mpic_request()
        # there are 3 rirs of 2 perspectives each in the test setup; expect 3 cohorts of 2 perspectives each
        request.orchestration_parameters = MpicRequestOrchestrationParameters(quorum_count=1, perspective_count=2, max_attempts=3)
        event = {'path': RequestPath.MPIC, 'body': json.dumps(request.model_dump())}
        # create mocks that will fail all attempts
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_failing_lambda_response, mpic_coordinator_config)
        result = mpic_coordinator.coordinate_mpic(event['body'])
        assert result['statusCode'] == 200
        mpic_response: MpicCaaResponse = self.mpic_response_adapter.validate_json(result['body'])
        assert mpic_response.is_valid is False
        assert mpic_response.actual_orchestration_parameters.attempt_count == 3

    def coordinate_mpic__should_cycle_through_perspective_cohorts_if_attempts_exceeds_cohort_number(self, set_env_variables, mocker):
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_successful_lambda_response, mpic_coordinator_config)

        first_request = ValidRequestCreator.create_valid_caa_mpic_request()
        # there are 3 rirs of 2 perspectives each in the test setup; expect 3 cohorts of 2 perspectives each
        first_request.orchestration_parameters = MpicRequestOrchestrationParameters(quorum_count=1, perspective_count=2, max_attempts=2)
        first_event = {'path': RequestPath.MPIC, 'body': json.dumps(first_request.model_dump())}
        # This mocking should probably be not lambda.
        # create mocks that will fail the first attempt and succeed for the second (1-2)
        #mocker.patch('aws_lambda_python.mpic_coordinator.mpic_coordinator.MpicCoordinator.thread_call',
        #             side_effect=TestMpicCoordinator.SideEffectForMockedPayloads(
        #                 self.create_failing_lambda_response, self.create_failing_lambda_response,
        #                 self.create_successful_lambda_response
        #             ))
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_successful_lambda_response_after_n_failures_closure(2), mpic_coordinator_config)
        first_result = mpic_coordinator.coordinate_mpic(first_event['body'])
        second_request = ValidRequestCreator.create_valid_caa_mpic_request()
        second_request.orchestration_parameters = MpicRequestOrchestrationParameters(quorum_count=1, perspective_count=2, max_attempts=5)
        second_event = {'path': RequestPath.MPIC, 'body': json.dumps(second_request.model_dump())}
        # create mocks that will fail the first four attempts and succeed for the fifth (loop back, 1-2-3-1-2)
        #mocker.patch('aws_la#mbda_python.mpic_coordinator.mpic_coordinator.MpicCoordinator.thread_call',
        #             side_effect=TestMpicCoordinator.SideEffectForMockedPayloads(
        #                 self.create_failing_lambda_response, self.create_failing_lambda_response,
        #                 self.create_failing_lambda_response, self.create_failing_lambda_response,
        #                 self.create_failing_lambda_response, self.create_failing_lambda_response,
        #                 self.create_failing_lambda_response, self.create_failing_lambda_response,
        #                 self.create_successful_lambda_response
        #             ))
        mpic_coordinator = MpicCoordinator(self.create_successful_lambda_response_after_n_failures_closure(8), mpic_coordinator_config)
        second_result = mpic_coordinator.coordinate_mpic(second_event['body'])
        first_cohort = self.mpic_response_adapter.validate_json(first_result['body']).perspectives
        second_cohort = self.mpic_response_adapter.validate_json(second_result['body']).perspectives
        # assert that perspectives in first cohort and in second cohort are the same perspectives
        assert all(first_cohort[i].perspective == second_cohort[i].perspective for i in range(len(first_cohort)))

    def coordinate_mpic__should_cap_attempts_at_max_attempts_env_parameter_if_found(self, set_env_variables, mocker):
        mpic_coordinator_configuration = self.create_mpic_coordinator_configuration()
        mpic_coordinator_configuration.global_max_attempts = 2
        request = ValidRequestCreator.create_valid_caa_mpic_request()
        # there are 3 rirs of 2 perspectives each in the test setup; expect 3 cohorts of 2 perspectives each
        request.orchestration_parameters = MpicRequestOrchestrationParameters(quorum_count=1, perspective_count=2,
                                                                              max_attempts=4)
        event = {'path': RequestPath.MPIC, 'body': json.dumps(request.model_dump())}
        # create mocks that will fail all attempts
        #mocker.patch('aws_lambda_python.mpic_coordinator.mpic_coordinator.MpicCoordinator.thread_call',
        #             side_effect=self.create_failing_lambda_response)
        mpic_coordinator = MpicCoordinator(self.create_failing_lambda_response, mpic_coordinator_configuration)
        result = mpic_coordinator.coordinate_mpic(event['body'])
        print(result)
        assert result['statusCode'] == 200
        mpic_response: MpicCaaResponse = self.mpic_response_adapter.validate_json(result['body'])
        assert mpic_response.is_valid is False
        assert mpic_response.actual_orchestration_parameters.attempt_count == 2
    

    def constructor__should_treat_max_attempts_as_optional_and_default_to_none(self, set_env_variables):
        mpic_coordinator_configuration = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_successful_lambda_response, mpic_coordinator_configuration)
        assert mpic_coordinator.global_max_attempts is None

    @pytest.mark.parametrize('check_type', [CheckType.CAA, CheckType.DCV, CheckType.DCV_WITH_CAA])
    def coordinate_mpic__should_return_check_failure_message_given_remote_perspective_failure(self, set_env_variables, check_type, mocker):
        request = None
        match check_type:
            case CheckType.CAA:
                request = ValidRequestCreator.create_valid_caa_mpic_request()
            case CheckType.DCV:
                request = ValidRequestCreator.create_valid_dcv_mpic_request()
            case CheckType.DCV_WITH_CAA:
                request = ValidRequestCreator.create_valid_dcv_with_caa_mpic_request()
        event = {'path': RequestPath.MPIC, 'body': json.dumps(request.model_dump())}
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_failing_lambda_response_that_thows_exception, mpic_coordinator_config)
        
        result = mpic_coordinator.coordinate_mpic(event['body'])
        assert result['statusCode'] == 200
        mpic_response = self.mpic_response_adapter.validate_json(result['body'])
        assert mpic_response.is_valid is False
        if check_type in [CheckType.CAA, CheckType.DCV]:
            perspectives_to_inspect = mpic_response.perspectives
        else:
            perspectives_to_inspect = mpic_response.perspectives_caa + mpic_response.perspectives_dcv
        for perspective in perspectives_to_inspect:
            assert perspective.check_passed is False
            assert perspective.errors[0].error_type == ErrorMessages.COORDINATOR_COMMUNICATION_ERROR.key

    @pytest.mark.skip(reason='This test should be moved to test the lambda function file since that now defines the reference to boto3.')
    def thread_call__should_call_lambda_function_with_correct_parameters(self, set_env_variables, mocker):
        mocker.patch('botocore.client.BaseClient._make_api_call', side_effect=self.create_successful_boto3_api_call_response)
        mpic_coordinator_configuration = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_successful_lambda_response, mpic_coordinator_configuration)
        mpic_coordinator = MpicCoordinator()
        mpic_request = ValidRequestCreator.create_valid_dcv_mpic_request()
        check_request = DcvCheckRequest(domain_or_ip_target='using.for.test',
                                        dcv_check_parameters=mpic_request.dcv_check_parameters)
        call_config = RemoteCheckCallConfiguration(CheckType.DCV, RemotePerspective(code='us-east-2', rir='arin'),
                                                   lambda_arn='test_arn', check_request=check_request)
        response = mpic_coordinator.thread_call(call_config)
        perspective_response = json.loads(response['Payload'].read().decode('utf-8'))
        perspective_response_body = json.loads(perspective_response['body'])
        check_response = DcvCheckResponse.model_validate(perspective_response_body)
        assert check_response.check_passed is True
        # hijacking the value of 'perspective' to verify that the right arguments got passed to the call
        assert check_response.perspective == check_request.domain_or_ip_target


    def create_mpic_coordinator_configuration(self):
        known_perspectives = os.environ['perspective_names'].split("|")
        default_perspective_count = int(os.environ['default_perspective_count'])
        enforce_distinct_rir_regions = int(os.environ['enforce_distinct_rir_regions']) == 1  # TODO may not need...
        global_max_attempts = int(os.environ['absolute_max_attempts']) if 'absolute_max_attempts' in os.environ else None
        hash_secret = os.environ['hash_secret']
        mpic_coordinator_configuration = MpicCoordinatorConfiguration(
            known_perspectives, 
            default_perspective_count, 
            enforce_distinct_rir_regions, 
            global_max_attempts, 
            hash_secret)
        return mpic_coordinator_configuration

    # This also can be used for call_remote_perspective
    def create_successful_lambda_response(self, perspective: RemotePerspective, check_type: CheckType, check_request_serialized: str):
        expected_response_body = CaaCheckResponse(perspective=perspective.to_rir_code(), check_passed=True,
                                                  details=CaaCheckResponseDetails(caa_record_present=False))
        return json.dumps(expected_response_body.model_dump())

    def create_successful_lambda_response_after_n_failures_closure(self, n: int):
        try_count = 0
        def res_function(perspective: RemotePerspective, check_type: CheckType, check_request_serialized: str):
            nonlocal try_count, n
            expected_response_body = None
            if try_count < n:
                expected_response_body = CaaCheckResponse(perspective=perspective.to_rir_code(), check_passed=False,
                                                  details=CaaCheckResponseDetails(caa_record_present=True))
                try_count += 1
            else:
                expected_response_body = CaaCheckResponse(perspective=perspective.to_rir_code(), check_passed=True,
                                                  details=CaaCheckResponseDetails(caa_record_present=False))
                try_count += 1
            return json.dumps(expected_response_body.model_dump())
        return res_function

    def create_failing_lambda_response(self, perspective: RemotePerspective, check_type: CheckType, check_request_serialized: str):
        expected_response_body = CaaCheckResponse(perspective=perspective.to_rir_code(), check_passed=False,
                                                  details=CaaCheckResponseDetails(caa_record_present=True))
        return json.dumps(expected_response_body.model_dump())
    
    def create_failing_lambda_response_that_thows_exception(self, perspective: RemotePerspective, check_type: CheckType, check_request_serialized: str):
        raise Exception("Something went wrong.")

    # noinspection PyUnusedLocal
    def create_error_lambda_response(self, call_config):
        # note: all perspective response details will be identical in these tests due to this mocking
        expected_response_body = 'Something went wrong'
        expected_response = {'statusCode': 500, 'body': expected_response_body}
        json_bytes = json.dumps(expected_response).encode('utf-8')
        file_like_response = io.BytesIO(json_bytes)
        streaming_body_response = StreamingBody(file_like_response, len(json_bytes))
        return {'Payload': streaming_body_response}

    # noinspection PyUnusedLocal
    def create_successful_boto3_api_call_response(self, lambda_method, lambda_configuration):
        check_request = DcvCheckRequest.model_validate_json(lambda_configuration['Payload'])
        # hijacking the value of 'perspective' to verify that the right arguments got passed to the call
        expected_response_body = DcvCheckResponse(perspective=check_request.domain_or_ip_target,
                                                  check_passed=True, details=DcvCheckResponseDetails())
        expected_response = {'statusCode': 200, 'body': json.dumps(expected_response_body.model_dump())}
        json_bytes = json.dumps(expected_response).encode('utf-8')
        file_like_response = io.BytesIO(json_bytes)
        streaming_body_response = StreamingBody(file_like_response, len(json_bytes))
        return {'Payload': streaming_body_response}

    class SideEffectForMockedPayloads:
        def __init__(self, *functions_to_call):
            self.functions_to_call = cycle(functions_to_call)

        def __call__(self, *args, **kwargs):
            function_to_call = next(self.functions_to_call)
            return function_to_call(*args, **kwargs)


if __name__ == '__main__':
    pytest.main()
