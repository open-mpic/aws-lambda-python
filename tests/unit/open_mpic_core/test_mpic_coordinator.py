from itertools import cycle
from unittest.mock import MagicMock

import pytest

from open_mpic_core.common_domain.check_response import CaaCheckResponse, CaaCheckResponseDetails
from open_mpic_core.common_domain.enum.dcv_validation_method import DcvValidationMethod
from open_mpic_core.common_domain.enum.check_type import CheckType
from open_mpic_core.common_domain.messages.ErrorMessages import ErrorMessages
from open_mpic_core.mpic_coordinator.domain.mpic_orchestration_parameters import MpicRequestOrchestrationParameters
from open_mpic_core.common_domain.remote_perspective import RemotePerspective
from open_mpic_core.mpic_coordinator.domain.mpic_request_validation_error import MpicRequestValidationError
from open_mpic_core.mpic_coordinator.mpic_coordinator import MpicCoordinator, MpicCoordinatorConfiguration

from unit.test_util.valid_mpic_request_creator import ValidMpicRequestCreator


# noinspection PyMethodMayBeStatic
class TestMpicCoordinator:
    def create_cohorts_of_randomly_selected_perspectives__should_throw_error_given_requested_count_exceeds_total_perspectives(self):
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        perspective_codes = mpic_coordinator_config.all_target_perspective_codes
        all_possible_perspectives_by_code = mpic_coordinator_config.all_possible_perspectives_by_code
        excessive_count = len(perspective_codes) + 1
        mpic_coordinator = MpicCoordinator(self.create_successful_remote_caa_check_response, mpic_coordinator_config)
        with pytest.raises(ValueError):
            mpic_coordinator.create_cohorts_of_randomly_selected_perspectives(perspective_codes, all_possible_perspectives_by_code,
                                                                              excessive_count, 'test_target')  # expect error

    def create_cohorts_of_randomly_selected_perspectives__should_return_list_of_cohorts_of_requested_size(self):
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        perspective_codes = mpic_coordinator_config.all_target_perspective_codes
        all_perspectives_by_code = mpic_coordinator_config.all_possible_perspectives_by_code
        cohort_size = len(perspective_codes) // 2
        mpic_coordinator = MpicCoordinator(self.create_successful_remote_caa_check_response, mpic_coordinator_config)
        cohorts = mpic_coordinator.create_cohorts_of_randomly_selected_perspectives(perspective_codes, all_perspectives_by_code,
                                                                                    cohort_size, 'test_target')
        assert len(cohorts) == 2

    @pytest.mark.parametrize('requested_perspective_count, expected_quorum_size', [(4, 3), (5, 4), (6, 4)])
    def determine_required_quorum_count__should_dynamically_set_required_quorum_count_given_no_quorum_specified(
            self, requested_perspective_count, expected_quorum_size):
        command = ValidMpicRequestCreator.create_valid_caa_mpic_request()
        command.orchestration_parameters.quorum_count = None
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_successful_remote_caa_check_response, mpic_coordinator_config)
        required_quorum_count = mpic_coordinator.determine_required_quorum_count(command.orchestration_parameters, requested_perspective_count)
        assert required_quorum_count == expected_quorum_size

    def determine_required_quorum_count__should_use_specified_quorum_count_given_quorum_specified(self):
        command = ValidMpicRequestCreator.create_valid_caa_mpic_request()
        command.orchestration_parameters.quorum_count = 5
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_successful_remote_caa_check_response, mpic_coordinator_config)
        required_quorum_count = mpic_coordinator.determine_required_quorum_count(command.orchestration_parameters, 6)
        assert required_quorum_count == 5

    def collect_async_calls_to_issue__should_have_only_caa_calls_given_caa_check_type(self):
        request = ValidMpicRequestCreator.create_valid_caa_mpic_request()
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        perspective_codes = mpic_coordinator_config.all_target_perspective_codes
        # for each perspective code, get the RemotePerspective object from all_possible_perspectives_by_code
        perspectives_to_use = [mpic_coordinator_config.all_possible_perspectives_by_code[perspective_code] for
                               perspective_code in perspective_codes]
        call_list = MpicCoordinator.collect_async_calls_to_issue(request, perspectives_to_use)
        assert len(call_list) == 6
        assert set(map(lambda call_result: call_result.check_type, call_list)) == {CheckType.CAA}  # ensure each call is of type 'caa'

    def collect_async_calls_to_issue__should_include_caa_check_parameters_as_caa_params_in_input_args_if_present(self):
        request = ValidMpicRequestCreator.create_valid_caa_mpic_request()
        request.caa_check_parameters.caa_domains = ['example.com']
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        perspective_codes = mpic_coordinator_config.all_target_perspective_codes
        # for each perspective code, get the RemotePerspective object from all_possible_perspectives_by_code
        perspectives_to_use = [mpic_coordinator_config.all_possible_perspectives_by_code[perspective_code] for
                               perspective_code in perspective_codes]
        call_list = MpicCoordinator.collect_async_calls_to_issue(request, perspectives_to_use)
        assert all(call.check_request.caa_check_parameters.caa_domains == ['example.com'] for call in call_list)

    def collect_async_calls_to_issue__should_have_only_dcv_calls_and_include_validation_input_args_given_dcv_check_type(self):
        request = ValidMpicRequestCreator.create_valid_dcv_mpic_request(DcvValidationMethod.DNS_GENERIC)
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        perspective_codes = mpic_coordinator_config.all_target_perspective_codes
        # for each perspective code, get the RemotePerspective object from all_possible_perspectives_by_code
        perspectives_to_use = [mpic_coordinator_config.all_possible_perspectives_by_code[perspective_code] for
                               perspective_code in perspective_codes]
        call_list = MpicCoordinator.collect_async_calls_to_issue(request, perspectives_to_use)
        assert len(call_list) == 6
        assert set(map(lambda call_result: call_result.check_type, call_list)) == {CheckType.DCV}  # ensure each call is of type 'dcv'
        assert all(call.check_request.dcv_check_parameters.validation_details.validation_method == DcvValidationMethod.DNS_GENERIC for call in call_list)
        assert all(call.check_request.dcv_check_parameters.validation_details.dns_name_prefix == 'test' for call in call_list)

    def collect_async_calls_to_issue__should_have_caa_and_dcv_calls_given_dcv_with_caa_check_type(self):
        request = ValidMpicRequestCreator.create_valid_dcv_with_caa_mpic_request()
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        perspective_codes = mpic_coordinator_config.all_target_perspective_codes
        # for each perspective code, get the RemotePerspective object from all_possible_perspectives_by_code
        perspectives_to_use = [mpic_coordinator_config.all_possible_perspectives_by_code[perspective_code] for
                               perspective_code in perspective_codes]
        call_list = MpicCoordinator.collect_async_calls_to_issue(request, perspectives_to_use)
        assert len(call_list) == 12
        # ensure the list contains both 'caa' and 'dcv' calls
        assert set(map(lambda call_result: call_result.check_type, call_list)) == {CheckType.CAA, CheckType.DCV}

    def coordinate_mpic__should_call_remote_perspective_call_function_with_correct_parameters(self):
        mpic_request = ValidMpicRequestCreator.create_valid_caa_mpic_request()
        mpic_request.orchestration_parameters = MpicRequestOrchestrationParameters(quorum_count=2, perspective_count=2,
                                                                                   max_attempts=2)
        mocked_remote_perspective_call_function = MagicMock()
        mocked_remote_perspective_call_function.side_effect = TestMpicCoordinator.SideEffectForMockedPayloads(
            self.create_successful_remote_caa_check_response, self.create_successful_remote_caa_check_response
        )
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(mocked_remote_perspective_call_function, mpic_coordinator_config)
        mpic_coordinator.coordinate_mpic(mpic_request)
        call_args_list = mocked_remote_perspective_call_function.call_args_list
        assert len(call_args_list) == 2
        for call in call_args_list:
            call_args = call.args
            remote_perspective: RemotePerspective = call_args[0]
            assert remote_perspective.code in mpic_coordinator_config.all_target_perspective_codes
            assert call_args[1] == mpic_request.check_type
            check_request = call_args[2]  # was previously a serialized string; now the actual CheckRequest object
            assert check_request.domain_or_ip_target == mpic_request.domain_or_ip_target

    def coordinate_mpic__should_return_200_and_results_given_successful_caa_corroboration(self):
        mpic_request = ValidMpicRequestCreator.create_valid_caa_mpic_request()
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_successful_remote_caa_check_response, mpic_coordinator_config)
        mpic_response = mpic_coordinator.coordinate_mpic(mpic_request)
        assert mpic_response.is_valid is True

    def coordinate_mpic__should_successfully_carry_out_caa_mpic_given_no_parameters_besides_target(self):
        mpic_request = ValidMpicRequestCreator.create_valid_caa_mpic_request()
        mpic_request.orchestration_parameters = None
        mpic_request.caa_check_parameters = None
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_successful_remote_caa_check_response, mpic_coordinator_config)
        mpic_response = mpic_coordinator.coordinate_mpic(mpic_request)
        assert mpic_response.is_valid is True

    def coordinate_mpic__should_successfully_carry_out_caa_mpic_given_empty_orchestration_parameters(self):
        mpic_request = ValidMpicRequestCreator.create_valid_caa_mpic_request()
        mpic_request.orchestration_parameters = MpicRequestOrchestrationParameters()
        mpic_request.caa_check_parameters = None
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_successful_remote_caa_check_response, mpic_coordinator_config)
        mpic_response = mpic_coordinator.coordinate_mpic(mpic_request)
        assert mpic_response.is_valid is True

    def coordinate_mpic__should_successfully_carry_out_caa_mpic_given_only_max_attempts_orchestration_parameters(self):
        mpic_request = ValidMpicRequestCreator.create_valid_caa_mpic_request()
        # Reset all fields in orchestration parameters to None
        mpic_request.orchestration_parameters = MpicRequestOrchestrationParameters()
        # Set max_attempts
        mpic_request.orchestration_parameters.max_attempts = 2
        mpic_request.caa_check_parameters = None
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_successful_remote_caa_check_response, mpic_coordinator_config)
        mpic_response = mpic_coordinator.coordinate_mpic(mpic_request)
        assert mpic_response.is_valid is True

    def coordinate_mpic__should_retry_corroboration_max_attempts_times_if_corroboration_fails(self):
        mpic_request = ValidMpicRequestCreator.create_valid_caa_mpic_request()
        # there are 3 rirs of 2 perspectives each in the test setup; expect 3 cohorts of 2 perspectives each
        mpic_request.orchestration_parameters = MpicRequestOrchestrationParameters(quorum_count=1, perspective_count=2, max_attempts=3)
        # create mocks that will fail the first two attempts and succeed for the third
        succeed_after_two_attempts = MagicMock()
        succeed_after_two_attempts.side_effect = TestMpicCoordinator.SideEffectForMockedPayloads(
            self.create_failing_remote_caa_check_response, self.create_failing_remote_caa_check_response,
            self.create_failing_remote_response_with_exception, self.create_failing_remote_response_with_exception,
            self.create_successful_remote_caa_check_response, self.create_successful_remote_caa_check_response
        )
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(succeed_after_two_attempts, mpic_coordinator_config)
        mpic_response = mpic_coordinator.coordinate_mpic(mpic_request)
        assert mpic_response.is_valid is True
        assert mpic_response.actual_orchestration_parameters.attempt_count == 3

    def coordinate_mpic__should_return_check_failure_if_max_attempts_were_reached_without_successful_check(self):
        mpic_request = ValidMpicRequestCreator.create_valid_caa_mpic_request()
        # there are 3 rirs of 2 perspectives each in the test setup; expect 3 cohorts of 2 perspectives each
        mpic_request.orchestration_parameters = MpicRequestOrchestrationParameters(quorum_count=1, perspective_count=2, max_attempts=3)
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        # "mock" the remote perspective call function to fail all attempts
        mpic_coordinator = MpicCoordinator(self.create_failing_remote_caa_check_response, mpic_coordinator_config)
        mpic_response = mpic_coordinator.coordinate_mpic(mpic_request)
        assert mpic_response.is_valid is False
        assert mpic_response.actual_orchestration_parameters.attempt_count == 3

    def coordinate_mpic__should_cycle_through_perspective_cohorts_if_attempts_exceeds_cohort_number(self):
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()

        first_request = ValidMpicRequestCreator.create_valid_caa_mpic_request()
        # there are 3 rirs of 2 perspectives each in the test setup; expect 3 cohorts of 2 perspectives each
        first_request.orchestration_parameters = MpicRequestOrchestrationParameters(quorum_count=1, perspective_count=2, max_attempts=2)
        # "mock" the remote perspective call function that will fail the first cohort and succeed for the second
        # (fail 1a, fail 1b, pass 2a, pass 2b)
        succeed_after_two_attempts = MagicMock()
        succeed_after_two_attempts.side_effect = TestMpicCoordinator.SideEffectForMockedPayloads(
            self.create_failing_remote_caa_check_response, self.create_failing_remote_caa_check_response,
            self.create_successful_remote_caa_check_response, self.create_successful_remote_caa_check_response
        )
        mpic_coordinator = MpicCoordinator(succeed_after_two_attempts, mpic_coordinator_config)
        first_response = mpic_coordinator.coordinate_mpic(first_request)
        first_cohort = first_response.perspectives
        first_cohort_sorted = sorted(first_cohort, key=lambda p: p.perspective)

        second_request = ValidMpicRequestCreator.create_valid_caa_mpic_request()
        second_request.orchestration_parameters = MpicRequestOrchestrationParameters(quorum_count=1, perspective_count=2, max_attempts=5)
        # "mock" the remote perspective call function that will fail the first four cohorts and succeed for the fifth
        # (loop back, 1-2-3-1-2, i.e., fail 1a+1b, fail 2a+2b, fail 3a+3b, fail 1a+1b again, pass 2a+2b)
        succeed_after_five_attempts = MagicMock()
        succeed_after_five_attempts.side_effect = TestMpicCoordinator.SideEffectForMockedPayloads(
            self.create_failing_remote_caa_check_response, self.create_failing_remote_caa_check_response,
            self.create_failing_remote_caa_check_response, self.create_failing_remote_caa_check_response,
            self.create_failing_remote_caa_check_response, self.create_failing_remote_caa_check_response,
            self.create_failing_remote_caa_check_response, self.create_failing_remote_caa_check_response,
            self.create_successful_remote_caa_check_response, self.create_successful_remote_caa_check_response
        )
        mpic_coordinator = MpicCoordinator(succeed_after_five_attempts, mpic_coordinator_config)
        second_response = mpic_coordinator.coordinate_mpic(second_request)
        second_cohort = second_response.perspectives
        second_cohort_sorted = sorted(second_cohort, key=lambda p: p.perspective)

        # assert that perspectives in first cohort and in second cohort are the same perspectives
        assert all(first_cohort_sorted[i].perspective == second_cohort_sorted[i].perspective for i in range(len(first_cohort_sorted)))

    def coordinate_mpic__should_cap_attempts_at_max_attempts_env_parameter_if_found(self):
        mpic_coordinator_configuration = self.create_mpic_coordinator_configuration()
        mpic_coordinator_configuration.global_max_attempts = 2
        mpic_request = ValidMpicRequestCreator.create_valid_caa_mpic_request()
        # there are 3 rirs of 2 perspectives each in the test setup; expect 3 cohorts of 2 perspectives each
        mpic_request.orchestration_parameters = MpicRequestOrchestrationParameters(quorum_count=1, perspective_count=2,
                                                                                   max_attempts=4)
        # "mock" a remote perspective call function that will fail all attempts
        mpic_coordinator = MpicCoordinator(self.create_failing_remote_caa_check_response, mpic_coordinator_configuration)
        mpic_response = mpic_coordinator.coordinate_mpic(mpic_request)
        assert mpic_response.is_valid is False
        assert mpic_response.actual_orchestration_parameters.attempt_count == 2

    @pytest.mark.parametrize('check_type', [CheckType.CAA, CheckType.DCV, CheckType.DCV_WITH_CAA])
    def coordinate_mpic__should_return_check_failure_message_given_remote_perspective_failure(self, check_type):
        mpic_request = None
        match check_type:
            case CheckType.CAA:
                mpic_request = ValidMpicRequestCreator.create_valid_caa_mpic_request()
            case CheckType.DCV:
                mpic_request = ValidMpicRequestCreator.create_valid_dcv_mpic_request()
            case CheckType.DCV_WITH_CAA:
                mpic_request = ValidMpicRequestCreator.create_valid_dcv_with_caa_mpic_request()
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_failing_remote_response_with_exception, mpic_coordinator_config)
        
        mpic_response = mpic_coordinator.coordinate_mpic(mpic_request)
        assert mpic_response.is_valid is False
        if check_type in [CheckType.CAA, CheckType.DCV]:
            perspectives_to_inspect = mpic_response.perspectives
        else:
            perspectives_to_inspect = mpic_response.perspectives_caa + mpic_response.perspectives_dcv
        for perspective in perspectives_to_inspect:
            assert perspective.check_passed is False
            assert perspective.errors[0].error_type == ErrorMessages.COORDINATOR_COMMUNICATION_ERROR.key

    def coordinate_mpic__should_raise_exception_given_logically_invalid_mpic_request(self):
        mpic_request = ValidMpicRequestCreator.create_valid_caa_mpic_request()
        mpic_request.orchestration_parameters = MpicRequestOrchestrationParameters(quorum_count=15, perspective_count=5,
                                                                                   max_attempts=1)
        mpic_request.domain_or_ip_target = None
        mpic_coordinator_config = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_successful_remote_caa_check_response, mpic_coordinator_config)
        with pytest.raises(MpicRequestValidationError):
            mpic_coordinator.coordinate_mpic(mpic_request)

    def constructor__should_treat_max_attempts_as_optional_and_default_to_none(self):
        mpic_coordinator_configuration = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_successful_remote_caa_check_response, mpic_coordinator_configuration)
        assert mpic_coordinator.global_max_attempts is None

    def constructor__should_set_configuration_and_remote_perspective_call_function(self):
        mpic_coordinator_configuration = self.create_mpic_coordinator_configuration()

        def call_remote_perspective():
            return 'this_is_a_dummy_response'

        mpic_coordinator = MpicCoordinator(call_remote_perspective, mpic_coordinator_configuration)
        assert mpic_coordinator.global_max_attempts == mpic_coordinator_configuration.global_max_attempts
        assert mpic_coordinator.all_target_perspective_codes == mpic_coordinator_configuration.all_target_perspective_codes
        assert mpic_coordinator.default_perspective_count == mpic_coordinator_configuration.default_perspective_count
        assert mpic_coordinator.enforce_distinct_rir_regions == mpic_coordinator_configuration.enforce_distinct_rir_regions
        assert mpic_coordinator.hash_secret == mpic_coordinator_configuration.hash_secret
        assert mpic_coordinator.call_remote_perspective_function == call_remote_perspective

    @staticmethod
    def create_mpic_coordinator_configuration() -> MpicCoordinatorConfiguration:
        target_perspective_codes = ['us-east-1', 'us-west-1',
                                    'eu-west-2', 'eu-central-2',
                                    'ap-northeast-1', 'ap-south-2']
        all_perspectives_by_code = TestMpicCoordinator.create_all_perspectives_by_code()
        default_perspective_count = 3
        enforce_distinct_rir_regions = True  # TODO may not need...
        global_max_attempts = None
        hash_secret = 'test_secret'
        mpic_coordinator_configuration = MpicCoordinatorConfiguration(
            all_perspectives_by_code,
            target_perspective_codes,
            default_perspective_count, 
            enforce_distinct_rir_regions, 
            global_max_attempts, 
            hash_secret)
        return mpic_coordinator_configuration

    @staticmethod
    def create_all_perspectives_by_code() -> dict[str, RemotePerspective]:
        perspectives = [
            RemotePerspective.from_rir_code('arin.us-east-1'),
            RemotePerspective.from_rir_code('arin.us-west-1'),
            RemotePerspective.from_rir_code('ripe.eu-west-2'),
            RemotePerspective.from_rir_code('ripe.eu-central-2'),
            RemotePerspective.from_rir_code('apnic.ap-northeast-1'),
            RemotePerspective.from_rir_code('apnic.ap-south-2')
        ]
        return {perspective.code: perspective for perspective in perspectives}

    # This also can be used for call_remote_perspective
    # noinspection PyUnusedLocal
    def create_successful_remote_caa_check_response(self, perspective: RemotePerspective, check_type: CheckType,
                                                    check_request_serialized: str):
        expected_response = CaaCheckResponse(perspective=perspective.to_rir_code(), check_passed=True,
                                             details=CaaCheckResponseDetails(caa_record_present=False))
        return expected_response

    # noinspection PyUnusedLocal
    def create_failing_remote_caa_check_response(self, perspective: RemotePerspective, check_type: CheckType,
                                                 check_request_serialized: str):
        expected_response = CaaCheckResponse(perspective=perspective.to_rir_code(), check_passed=False,
                                             details=CaaCheckResponseDetails(caa_record_present=True))
        return expected_response

    # noinspection PyUnusedLocal
    def create_failing_remote_response_with_exception(self, perspective: RemotePerspective, check_type: CheckType,
                                                      check_request_serialized: str):
        raise Exception("Something went wrong.")

    class SideEffectForMockedPayloads:
        def __init__(self, *functions_to_call):
            self.functions_to_call = cycle(functions_to_call)

        def __call__(self, *args, **kwargs):
            function_to_call = next(self.functions_to_call)
            return function_to_call(*args, **kwargs)


if __name__ == '__main__':
    pytest.main()
