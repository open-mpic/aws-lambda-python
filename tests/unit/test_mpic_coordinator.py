import io
import json
from itertools import chain, cycle
from pprint import pprint

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
from aws_lambda_python.mpic_coordinator.domain.remote_perspective import RemotePerspective
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
        cls.all_perspectives_per_rir = TestMpicCoordinator.set_up_perspectives_per_rir_dict_from_file()

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

    # @pytest.mark.skip('This test is not yet implemented')
    @pytest.mark.parametrize('perspectives_per_rir, any_perspectives_too_close, cohort_size', [
        # perspectives_per_rir expects: (total_perspectives, total_rirs, max_per_rir, too_close_flag)
        ((3, 2, 2, False), False, 1),  # expect 3 cohorts of 1
        ((3, 2, 2, False), False, 2),  # expect 1 cohort of 2
        ((5, 2, 4, False), False, 5),  # expect 1 cohort of 5
        ((6, 3, 2, False), False, 2),  # expect 3 cohorts of 2
        ((6, 3, 2, True), True, 2),  # expect 3 cohorts of 2
        ((10, 2, 5, False), False, 5),  # expect 2 cohorts of 5
        ((10, 2, 5, True), True, 4),  # expect 2 cohorts of 4
        ((18, 5, 8, True), True, 6),  # expect 3 cohorts of 6
        ((18, 5, 8, False), False, 6),  # expect 3 cohorts of 6
        ((18, 3, 6, True), True, 6),   # expect 3 cohorts of 6
        ((18, 5, 7, True), True, 15),  # expect 1 cohort of 15
    ], indirect=['perspectives_per_rir'])
    def create_perspective_cohorts__should_return_set_of_cohorts_with_requested_size(self, perspectives_per_rir,
                                                                                     any_perspectives_too_close, cohort_size):
        total_perspectives = len(list(chain.from_iterable(perspectives_per_rir.values())))
        print(f"\ntotal perspectives: {total_perspectives}")
        print(f"total rirs: {len(perspectives_per_rir.keys())}")
        print(f"any perspectives too close: {any_perspectives_too_close}")
        pprint(perspectives_per_rir)
        cohorts = MpicCoordinator.create_perspective_cohorts(perspectives_per_rir, cohort_size)
        print(f"total cohorts created: {len(cohorts)}")
        pprint(cohorts)
        assert len(cohorts) > 0
        if not any_perspectives_too_close:  # if no perspectives were too close, should have max possible cohorts
            assert len(cohorts) == total_perspectives // cohort_size
        for cohort in cohorts:
            assert len(cohort) == cohort_size
            # assert that no two perspectives in the cohort are too close to each other
            for i in range(len(cohort)):
                for j in range(i + 1, len(cohort)):
                    assert not cohort[i].is_perspective_too_close(cohort[j])
            # assert that all cohorts have at least 2 RIRs (unless desired cohort size is 1)
            if cohort_size > 1:
                assert len(set(map(lambda perspective: perspective.rir, cohort))) >= 2

    @pytest.mark.skip(reason='This test is not yet implemented')
    def create_perspective_cohorts__should_return_multiple_disjoint_cohorts_with_multiple_rirs_in_each(self, perspectives_per_rir, cohort_size):
        cohorts = MpicCoordinator.create_perspective_cohorts(perspectives_per_rir, cohort_size)
        assert len(cohorts) == 3
        assert all(len(cohort) == 2 for cohort in cohorts)

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
        loaded_aws_regions = MpicCoordinator.load_aws_region_config()
        all_perspectives = list(chain.from_iterable(self.all_perspectives_per_rir.values()))
        assert len(loaded_aws_regions.keys()) == len(all_perspectives)
        # for example, us-east-1 is too close to us-east-2
        assert 'us-east-2' in loaded_aws_regions['us-east-1'].too_close_codes
        assert 'us-east-1' in loaded_aws_regions['us-east-2'].too_close_codes

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

    @staticmethod
    def set_up_perspectives_per_rir_dict_from_file():
        perspectives_yaml = yaml.safe_load(pkg_resources.open_text('resources', 'aws_region_config.yaml'))
        perspective_type_adapter = TypeAdapter(list[RemotePerspective])
        perspectives = perspective_type_adapter.validate_python(perspectives_yaml['aws_available_regions'])
        # get set of unique rirs from perspectives, each of which has a rir attribute
        all_rirs = set(map(lambda perspective: perspective.rir, perspectives))
        return {rir: [perspective for perspective in perspectives if perspective.rir == rir] for rir in all_rirs}

    @pytest.fixture
    def perspectives_per_rir(self, request):
        total_perspectives = request.param[0]
        total_rirs = request.param[1]
        max_per_rir = request.param[2]
        too_close_flag = request.param[3]
        return self.create_perspectives_per_rir_given_requirements(total_perspectives, total_rirs, max_per_rir, too_close_flag)

    def create_perspectives_per_rir_given_requirements(self, total_perspectives, total_rirs, max_per_rir, too_close_flag):
        # get set (unique) of all rirs found in all_available_perspectives, each of which has a rir attribute
        perspectives_per_rir = dict[str, list[RemotePerspective]]()
        total_perspectives_added = 0
        # set ordered_rirs to be a list of rirs ordered in descending order based on number of perspectives for each rir in all_perspectives_per_rir
        all_rirs = list(self.all_perspectives_per_rir.keys())
        all_rirs.sort(key=lambda rir: len(self.all_perspectives_per_rir[rir]), reverse=True)
        while len(all_rirs) > total_rirs:
            all_rirs.pop()
        # in case total_perspectives is too high for the number actually available in the rirs left
        max_available_perspectives = sum(len(self.all_perspectives_per_rir[rir]) for rir in all_rirs)

        rirs_cycle = cycle(all_rirs)
        while total_perspectives_added < total_perspectives and total_perspectives_added < max_available_perspectives:
            current_rir = next(rirs_cycle)
            all_perspectives_for_rir: list[RemotePerspective] = list(self.all_perspectives_per_rir[current_rir])
            if current_rir not in perspectives_per_rir.keys():
                perspectives_per_rir[current_rir] = []
            while (len(perspectives_per_rir[current_rir]) < max_per_rir
                   and len(all_perspectives_for_rir) > 0
                   and total_perspectives_added < total_perspectives):
                if too_close_flag and len(perspectives_per_rir[current_rir]) == 0:
                    # find two perspectives in all_perspectives_for_rir that are too close to each other
                    first_too_close_index = 0
                    first_too_close_perspective = None
                    second_too_close_index = 0
                    for i in range(len(all_perspectives_for_rir)):
                        if len(all_perspectives_for_rir[i].too_close_codes) > 0:
                            first_too_close_index = i
                            first_too_close_perspective = all_perspectives_for_rir[i]
                            break
                    for j in range(first_too_close_index + 1, len(all_perspectives_for_rir)):
                        if first_too_close_perspective.is_perspective_too_close(all_perspectives_for_rir[j]):
                            second_too_close_index = j
                            break
                    if second_too_close_index > 0:  # found two too close perspectives
                        # pop the later one first so that the earlier one is not affected by the index change
                        perspectives_per_rir[current_rir].append(all_perspectives_for_rir.pop(second_too_close_index))
                        perspectives_per_rir[current_rir].append(all_perspectives_for_rir.pop(first_too_close_index))
                        total_perspectives_added += 2
                        continue

                perspective_to_add = all_perspectives_for_rir.pop(0)
                if not any(perspective_to_add.is_perspective_too_close(perspective) for perspective in perspectives_per_rir[current_rir]):
                    perspectives_per_rir[current_rir].append(perspective_to_add)
                    total_perspectives_added += 1
                else:
                    continue

        return perspectives_per_rir


if __name__ == '__main__':
    pytest.main()
