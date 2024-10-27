import json
import traceback
from itertools import cycle

import time
import concurrent.futures
from datetime import datetime
import os
import hashlib
import pydantic

from aws_lambda_python.common_domain.check_response import CheckResponse, AnnotatedCheckResponse, CaaCheckResponse, \
    CaaCheckResponseDetails, DcvCheckResponse, DcvCheckResponseDetails
from aws_lambda_python.common_domain.check_request import CaaCheckRequest, DcvCheckRequest
from aws_lambda_python.common_domain.validation_error import ValidationError
from aws_lambda_python.common_domain.enum.check_type import CheckType
from aws_lambda_python.common_domain.messages.ErrorMessages import ErrorMessages
from aws_lambda_python.mpic_coordinator.cohort_creator import CohortCreator
from aws_lambda_python.mpic_coordinator.domain.mpic_request import MpicCaaRequest, MpicRequest, AnnotatedMpicRequest
from aws_lambda_python.mpic_coordinator.domain.mpic_request import MpicDcvRequest, MpicDcvWithCaaRequest
from aws_lambda_python.mpic_coordinator.domain.remote_check_call_configuration import RemoteCheckCallConfiguration
from aws_lambda_python.mpic_coordinator.domain.enum.request_path import RequestPath
from aws_lambda_python.mpic_coordinator.domain.remote_perspective import RemotePerspective
from aws_lambda_python.mpic_coordinator.messages.mpic_request_validation_messages import MpicRequestValidationMessages
from aws_lambda_python.mpic_coordinator.mpic_request_validator import MpicRequestValidator
from aws_lambda_python.mpic_coordinator.mpic_response_builder import MpicResponseBuilder
from pydantic import TypeAdapter


class MpicCoordinatorConfiguration:
    def __init__(self, known_perspectives, default_perspective_count, enforce_distinct_rir_regions, global_max_attempts, hash_secret):
        self.known_perspectives = known_perspectives
        self.default_perspective_count = default_perspective_count
        self.enforce_distinct_rir_regions = enforce_distinct_rir_regions
        self.global_max_attempts = global_max_attempts
        self.hash_secret = hash_secret



class MpicCoordinator:
    def __init__(self, call_remote_perspective_funtion, mpic_coordinator_configuration: MpicCoordinatorConfiguration):
        self.known_perspectives = mpic_coordinator_configuration.known_perspectives

        self.default_perspective_count = mpic_coordinator_configuration.default_perspective_count
        self.enforce_distinct_rir_regions = mpic_coordinator_configuration.enforce_distinct_rir_regions
        self.global_max_attempts = mpic_coordinator_configuration.global_max_attempts
        self.hash_secret = mpic_coordinator_configuration.hash_secret
        # TODO fix config.yaml to use snake_case for keys
        self.call_remote_perspective_funtion = call_remote_perspective_funtion
        
        # for correct deserialization of responses based on discriminator field (check type)
        self.mpic_request_adapter: TypeAdapter[MpicRequest] = TypeAdapter(AnnotatedMpicRequest)
        self.check_response_adapter: TypeAdapter[CheckResponse] = TypeAdapter(AnnotatedCheckResponse)

    def coordinate_mpic(self, body):
        # Path validation should be done by whatever is calling lib-open-mpic.
        #request_path = event['path']
        #if request_path not in iter(RequestPath):
        #    return MpicCoordinator.build_400_response(MpicRequestValidationMessages.REQUEST_VALIDATION_FAILED.key,
        #                                              [MpicRequestValidationMessages.UNSUPPORTED_REQUEST_PATH.key])

        # parse event body into mpic_request
        try:
            mpic_request = self.mpic_request_adapter.validate_json(body)
        except pydantic.ValidationError as validation_error:
            return MpicCoordinator.build_400_response(MpicRequestValidationMessages.REQUEST_VALIDATION_FAILED.key,
                                                      validation_error.errors())

        is_request_valid, validation_issues = MpicRequestValidator.is_request_valid(mpic_request, self.known_perspectives)

        if not is_request_valid:
            return MpicCoordinator.build_400_response(MpicRequestValidationMessages.REQUEST_VALIDATION_FAILED.key,
                                                      [vars(issue) for issue in validation_issues])

        orchestration_parameters = mpic_request.orchestration_parameters

        # Determine the perspectives and perspective count to use for this request.
        # TODO revisit this when diagnostic mode (allowing 'perspectives') is implemented
        perspective_count = self.default_perspective_count
        if orchestration_parameters is not None:
            if orchestration_parameters.perspectives is not None:
                perspectives_to_use = orchestration_parameters.perspectives
                perspective_count = len(perspectives_to_use)
            else:
                if orchestration_parameters.perspective_count is not None:
                    perspective_count = orchestration_parameters.perspective_count

        perspective_cohorts = self.create_cohorts_of_randomly_selected_perspectives(self.known_perspectives,
                                                                                    perspective_count,
                                                                                    mpic_request.domain_or_ip_target)

        quorum_count = self.determine_required_quorum_count(orchestration_parameters, perspective_count)

        if orchestration_parameters is not None and orchestration_parameters.max_attempts is not None:
            max_attempts = orchestration_parameters.max_attempts
            if self.global_max_attempts is not None and max_attempts > self.global_max_attempts:
                max_attempts = self.global_max_attempts
        else:
            max_attempts = 1
        attempts = 1
        cohort_cycle = cycle(perspective_cohorts)
        while attempts <= max_attempts:
            perspectives_to_use = next(cohort_cycle)

            # Collect async calls to invoke for each perspective.
            async_calls_to_issue = self.collect_async_calls_to_issue(mpic_request, perspectives_to_use)

            perspective_responses_per_check_type, validity_per_perspective_per_check_type = (
                self.issue_async_calls_and_collect_responses(perspectives_to_use, async_calls_to_issue))

            valid_by_check_type = {}
            for check_type in [CheckType.CAA, CheckType.DCV]:
                valid_perspective_count = sum(validity_per_perspective_per_check_type[check_type].values())
                valid_by_check_type[check_type] = valid_perspective_count >= quorum_count

            if MpicCoordinator.are_checks_valid(mpic_request.check_type, valid_by_check_type) or attempts == max_attempts:
                response = MpicResponseBuilder.build_response(mpic_request, perspective_count, quorum_count, attempts,
                                                              perspective_responses_per_check_type, valid_by_check_type)
                return response
            else:
                attempts += 1

    # Returns a random subset of perspectives with a goal of maximum RIR diversity to increase diversity.
    # Perspectives must be of the form 'RIR.AWS-region'.
    def create_cohorts_of_randomly_selected_perspectives(self, available_perspectives_as_strings, count, domain_or_ip_target):
        if count > len(available_perspectives_as_strings):
            raise ValueError(
                f"Count ({count}) must be <= the number of available perspectives ({available_perspectives_as_strings})")

        random_seed = hashlib.sha256((self.hash_secret + domain_or_ip_target.lower()).encode('ASCII')).digest()
        perspectives_per_rir = CohortCreator.build_randomly_shuffled_available_perspectives_per_rir(available_perspectives_as_strings, random_seed)
        cohorts = CohortCreator.create_perspective_cohorts(perspectives_per_rir, count)
        return cohorts

    # Determines the minimum required quorum size if none is specified in the request.
    @staticmethod
    def determine_required_quorum_count(orchestration_parameters, perspective_count):
        if orchestration_parameters is not None and orchestration_parameters.quorum_count is not None:
            required_quorum_count = orchestration_parameters.quorum_count
        else:
            required_quorum_count = perspective_count - 1 if perspective_count <= 5 else perspective_count - 2
        return required_quorum_count

    # Configures the async lambda function calls to issue for the check request.
    def collect_async_calls_to_issue(self, mpic_request, perspectives_to_use: list[RemotePerspective]) -> list[RemoteCheckCallConfiguration]:
        domain_or_ip_target = mpic_request.domain_or_ip_target
        async_calls_to_issue = []

        # check if mpic_request is an instance of MpicDcvWithCaaRequest, MpicCaaRequest, or MpicDcvRequest
        if isinstance(mpic_request, MpicDcvWithCaaRequest) or isinstance(mpic_request, MpicCaaRequest):
            check_parameters = CaaCheckRequest(domain_or_ip_target=domain_or_ip_target, caa_check_parameters=mpic_request.caa_check_parameters)
            for perspective in perspectives_to_use:
                # key is of the form 'RIR.AWS-region'
                call_config = RemoteCheckCallConfiguration(CheckType.CAA, perspective, check_parameters)
                async_calls_to_issue.append(call_config)

        if isinstance(mpic_request, MpicDcvWithCaaRequest) or isinstance(mpic_request, MpicDcvRequest):
            check_parameters = DcvCheckRequest(domain_or_ip_target=domain_or_ip_target, dcv_check_parameters=mpic_request.dcv_check_parameters)
            for perspective in perspectives_to_use:
                # key is of the form 'RIR.AWS-region'
                call_config = RemoteCheckCallConfiguration(CheckType.DCV, perspective, check_parameters)
                async_calls_to_issue.append(call_config)

        return async_calls_to_issue

    # Issues the async calls to the lambda functions and collects the responses.
    def issue_async_calls_and_collect_responses(self, perspectives_to_use, async_calls_to_issue) -> (dict, dict):
        perspective_responses_per_check_type = {}
        validity_per_perspective_per_check_type = {
            CheckType.CAA: {perspective.to_rir_code(): False for perspective in perspectives_to_use},
            CheckType.DCV: {perspective.to_rir_code(): False for perspective in perspectives_to_use}
        }

        perspective_count = len(perspectives_to_use)

        # example code: https://docs.python.org/3/library/concurrent.futures.html
        with concurrent.futures.ThreadPoolExecutor(max_workers=perspective_count) as executor:
            exec_begin = time.perf_counter()
            futures_to_call_configs = {executor.submit(self.thread_call, self.call_remote_perspective_funtion, call_config): call_config for call_config in
                                       async_calls_to_issue}
            for future in concurrent.futures.as_completed(futures_to_call_configs):
                call_configuration = futures_to_call_configs[future]
                perspective: RemotePerspective = call_configuration.perspective
                check_type = call_configuration.check_type
                now = time.perf_counter()
                print(
                    f"Unpacking future result for {perspective.to_rir_code()} at time {str(datetime.now())}: {now - exec_begin:.2f} \
                    seconds from beginning")
                try:
                    data = future.result()
                except Exception as e:
                    stacktrace = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
                    print(f'{perspective.to_rir_code()} generated an exception: {stacktrace}')
                else:
                    if check_type not in perspective_responses_per_check_type:
                        perspective_responses_per_check_type[check_type] = []
                    try:
                        perspective_response = json.loads(data['Payload'].read().decode('utf-8'))
                        print(perspective_response)
                        perspective_response_body = json.loads(perspective_response['body'])
                        # deserialize perspective body to have a nested object in the output rather than a string
                        check_response = self.check_response_adapter.validate_python(perspective_response_body)
                        validity_per_perspective_per_check_type[check_type][perspective.to_rir_code()] |= check_response.check_passed
                        # TODO make sure responses per perspective match API spec...
                        perspective_responses_per_check_type[check_type].append(check_response)
                    except Exception:  # TODO what exceptions are we expecting here?
                        print(traceback.format_exc())
                        match check_type:
                            case CheckType.CAA:
                                check_error_response = CaaCheckResponse(
                                    perspective=perspective.to_rir_code(),
                                    check_passed=False,
                                    errors=[ValidationError(error_type=ErrorMessages.COORDINATOR_COMMUNICATION_ERROR.key,
                                                            error_message=ErrorMessages.COORDINATOR_COMMUNICATION_ERROR.message)],
                                    details=CaaCheckResponseDetails(caa_record_present=False),  # TODO Possibly should None to indicate the lookup failed.
                                    timestamp_ns=time.time_ns()
                                )
                            case CheckType.DCV:
                                check_error_response = DcvCheckResponse(
                                    perspective=perspective.to_rir_code(),
                                    check_passed=False,
                                    errors=[ValidationError(error_type=ErrorMessages.COORDINATOR_COMMUNICATION_ERROR.key,
                                                            error_message=ErrorMessages.COORDINATOR_COMMUNICATION_ERROR.message)],
                                    details=DcvCheckResponseDetails(),  # TODO what should go here in this case?
                                    timestamp_ns=time.time_ns()
                                )
                        validity_per_perspective_per_check_type[check_type][perspective.to_rir_code()] |= check_error_response.check_passed
                        perspective_responses_per_check_type[check_type].append(check_error_response)
        return perspective_responses_per_check_type, validity_per_perspective_per_check_type

    @staticmethod
    def build_400_response(error_name, issues_list):
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': error_name, 'validation_issues': issues_list})
        }

    @staticmethod
    def thread_call(call_remote_perspective_funtion, call_config: RemoteCheckCallConfiguration):
        """
        Issues a call to a lambda function in a separate thread. This is a blocking call.
        This is purely AWS specific and should not be used in other contexts.
        :param call_config:
        :return:
        """
        print(f"Started lambda call for region {call_config.perspective} at {str(datetime.now())}")

        tic_init = time.perf_counter()
        # get region from perspective
        # TODO get better coverage for this function
        #client = boto3.client('lambda', call_config.perspective.code)
        tic = time.perf_counter()
        response = call_remote_perspective_funtion(call_config)
        #response = client.invoke(  # AWS Lambda-specific structure
        #    FunctionName=call_config.lambda_arn,
        #    InvocationType='RequestResponse',
        #    Payload=json.dumps()
        #)
        toc = time.perf_counter()

        print(f"Response in region {call_config.perspective.to_rir_code()} took {toc - tic:0.4f} seconds to get response; \
              {tic - tic_init:.2f} seconds to start boto client; ended at {str(datetime.now())}\n")
        return response

    @staticmethod
    def are_checks_valid(check_type, validity_by_check_type) -> bool:
        match check_type:
            case CheckType.CAA:
                return validity_by_check_type[CheckType.CAA]
            case CheckType.DCV:
                return validity_by_check_type[CheckType.DCV]
            case CheckType.DCV_WITH_CAA:
                return validity_by_check_type[CheckType.DCV] and validity_by_check_type[CheckType.CAA]
