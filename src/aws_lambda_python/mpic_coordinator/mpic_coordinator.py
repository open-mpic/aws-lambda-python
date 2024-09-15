import json
import traceback
from itertools import cycle, chain

import boto3
import time
import concurrent.futures
from datetime import datetime
import os
import random
import hashlib
import pydantic
import importlib.resources as pkg_resources
import yaml

from aws_lambda_python.common_domain.check_response import CheckResponse, AnnotatedCheckResponse, CaaCheckResponse, \
    CaaCheckResponseDetails, DcvCheckResponse, DcvCheckResponseDetails
from aws_lambda_python.common_domain.check_request import CaaCheckRequest
from aws_lambda_python.common_domain.check_request import DcvCheckRequest
from aws_lambda_python.common_domain.validation_error import ValidationError
from aws_lambda_python.common_domain.enum.check_type import CheckType
from aws_lambda_python.common_domain.messages.ErrorMessages import ErrorMessages
from aws_lambda_python.mpic_coordinator.domain.remote_perspective import RemotePerspective
from aws_lambda_python.mpic_coordinator.domain.mpic_request import MpicCaaRequest, MpicRequest, AnnotatedMpicRequest
from aws_lambda_python.mpic_coordinator.domain.mpic_request import MpicDcvRequest
from aws_lambda_python.mpic_coordinator.domain.mpic_request import MpicDcvWithCaaRequest
from aws_lambda_python.mpic_coordinator.domain.remote_check_call_configuration import RemoteCheckCallConfiguration
from aws_lambda_python.mpic_coordinator.domain.enum.request_path import RequestPath
from aws_lambda_python.mpic_coordinator.messages.mpic_request_validation_messages import MpicRequestValidationMessages
from aws_lambda_python.mpic_coordinator.mpic_request_validator import MpicRequestValidator
from aws_lambda_python.mpic_coordinator.mpic_response_builder import MpicResponseBuilder
from pydantic import TypeAdapter


class MpicCoordinator:
    def __init__(self):
        # Load lists of perspective names, validator arns, and caa arns from environment vars.
        self.known_perspectives = os.environ['perspective_names'].split("|")
        self.dcv_arn_list = os.environ['validator_arns'].split("|")  # TODO rename to dcv_arns
        self.caa_arn_list = os.environ['caa_arns'].split("|")
        self.default_perspective_count = int(os.environ['default_perspective_count'])
        self.enforce_distinct_rir_regions = int(os.environ['enforce_distinct_rir_regions']) == 1
        self.hash_secret = os.environ['hash_secret']

        # Create a dictionary of ARNs per check type per perspective to simplify lookup in the future.
        # (Assumes known_perspectives list, validator_arn_list, and caa_arn_list are the same length.)
        self.arns_per_perspective_per_check_type = {
            CheckType.DCV: {self.known_perspectives[i]: self.dcv_arn_list[i] for i in range(len(self.known_perspectives))},
            CheckType.CAA: {self.known_perspectives[i]: self.caa_arn_list[i] for i in range(len(self.known_perspectives))}
        }
        # for correct deserialization of responses based on discriminator field (check type)
        self.mpic_request_adapter: TypeAdapter[MpicRequest] = TypeAdapter(AnnotatedMpicRequest)
        self.check_response_adapter: TypeAdapter[CheckResponse] = TypeAdapter(AnnotatedCheckResponse)

    def coordinate_mpic(self, event):
        request_path = event['path']
        if request_path not in iter(RequestPath):
            return MpicCoordinator.build_400_response(MpicRequestValidationMessages.REQUEST_VALIDATION_FAILED.key,
                                                      [MpicRequestValidationMessages.UNSUPPORTED_REQUEST_PATH.key])

        # parse event body into mpic_request
        try:
            mpic_request = self.mpic_request_adapter.validate_json(event['body'])
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
        perspectives_to_use = self.select_random_perspectives_across_rirs(self.known_perspectives,
                                                                          perspective_count,
                                                                          mpic_request.domain_or_ip_target)

        quorum_count = self.determine_required_quorum_count(orchestration_parameters, perspective_count)

        # Collect async calls to invoke for each perspective.
        async_calls_to_issue = self.collect_async_calls_to_issue(mpic_request, perspectives_to_use)

        perspective_responses_per_check_type, validity_per_perspective_per_check_type = (
            self.issue_async_calls_and_collect_responses(perspectives_to_use, async_calls_to_issue))

        valid_by_check_type = {}
        for check_type in [CheckType.CAA, CheckType.DCV]:
            valid_perspective_count = sum(validity_per_perspective_per_check_type[check_type].values())

            # TODO enforce requirement of 2+ RIRs in corroborating perspective set
            # TODO enforce requirement of 500km distances between all corroborating perspectives
            valid_by_check_type[check_type] = valid_perspective_count >= quorum_count

        response = MpicResponseBuilder.build_response(mpic_request, perspective_count, quorum_count,
                                                      perspective_responses_per_check_type, valid_by_check_type)

        return response

    # Returns a random subset of perspectives with a goal of maximum RIR diversity to increase diversity.
    # Perspectives must be of the form 'RIR.AWS-region'.
    def select_random_perspectives_across_rirs(self, available_perpectives_as_strings, count, domain_or_ip_target):
        if count > len(available_perpectives_as_strings):
            raise ValueError(
                f"Count ({count}) must be <= the number of available perspectives ({available_perpectives_as_strings})")

        # self.aws_region_config = MpicCoordinator.load_aws_region_config()  # TODO use this list for RIR/km rules

        # Create list of region objects from perspective strings
        available_perspectives = []
        for perspective in available_perpectives_as_strings:
            perspective_parts = perspective.split('.')
            available_perspectives.append(RemotePerspective(code=perspective_parts[1], rir=perspective_parts[0]))

        # Compute the distinct list or RIRs from all perspectives being considered.
        rirs_available = list(set([perspective.rir for perspective in available_perspectives]))

        # TODO implement perspective cohort selection logic for floor(perspectives/count) > 1

        # Seed the random generator with the hash secret concatenated with the domain-or-ip-target in all lowercase.
        # This prevents the adversary from gaining an advantage by retrying and getting different vantage point sets.
        random.seed(hashlib.sha256((self.hash_secret + domain_or_ip_target.lower()).encode('ASCII')).digest())

        # Get a random ordering of RIRs
        random.shuffle(rirs_available)

        # Create a list of lists, grouping perspectives by their RIR.
        perspectives_per_rir = {
            rir: [region for region in available_perspectives if region.rir == rir] for rir in rirs_available
        }

        # RIR index loops through the different RIRs and adds a single chosen perspective from each RIR on each iteration.
        chosen_perspectives = []
        rirs_cycle = cycle(rirs_available)
        while len(chosen_perspectives) < count:
            next_rir = next(rirs_cycle)
            if len(perspectives_per_rir[next_rir]) >= 1:
                chosen_perspective = random.choice(perspectives_per_rir[next_rir])
                chosen_perspectives.append(chosen_perspective.region_id())
                perspectives_per_rir[next_rir].remove(chosen_perspective)
        return chosen_perspectives

    # Determines the minimum required quorum size if none is specified in the request.
    @staticmethod
    def determine_required_quorum_count(orchestration_parameters, perspective_count):
        if orchestration_parameters is not None and orchestration_parameters.quorum_count is not None:
            required_quorum_count = orchestration_parameters.quorum_count
        else:
            required_quorum_count = perspective_count - 1 if perspective_count <= 5 else perspective_count - 2
        return required_quorum_count

    # Configures the async lambda function calls to issue for the check request.
    def collect_async_calls_to_issue(self, mpic_request, perspectives_to_use) -> list[RemoteCheckCallConfiguration]:
        domain_or_ip_target = mpic_request.domain_or_ip_target
        async_calls_to_issue = []

        # check if mpic_request is an instance of MpicDcvWithCaaRequest, MpicCaaRequest, or MpicDcvRequest
        if isinstance(mpic_request, MpicDcvWithCaaRequest) or isinstance(mpic_request, MpicCaaRequest):
            check_parameters = CaaCheckRequest(domain_or_ip_target=domain_or_ip_target, caa_check_parameters=mpic_request.caa_check_parameters)
            for perspective in perspectives_to_use:
                arn = self.arns_per_perspective_per_check_type[CheckType.CAA][perspective]
                call_config = RemoteCheckCallConfiguration(CheckType.CAA, perspective, arn, check_parameters)
                async_calls_to_issue.append(call_config)

        if isinstance(mpic_request, MpicDcvWithCaaRequest) or isinstance(mpic_request, MpicDcvRequest):
            check_parameters = DcvCheckRequest(domain_or_ip_target=domain_or_ip_target, dcv_check_parameters=mpic_request.dcv_check_parameters)
            for perspective in perspectives_to_use:
                arn = self.arns_per_perspective_per_check_type[CheckType.DCV][perspective]
                call_config = RemoteCheckCallConfiguration(CheckType.DCV, perspective, arn, check_parameters)
                async_calls_to_issue.append(call_config)

        return async_calls_to_issue

    # Issues the async calls to the lambda functions and collects the responses.
    def issue_async_calls_and_collect_responses(self, perspectives_to_use, async_calls_to_issue) -> (dict, dict):
        perspective_responses_per_check_type = {}
        validity_per_perspective_per_check_type = {CheckType.CAA: {r: False for r in perspectives_to_use},
                                                   CheckType.DCV: {r: False for r in perspectives_to_use}}

        perspective_count = len(perspectives_to_use)

        # example code: https://docs.python.org/3/library/concurrent.futures.html
        with concurrent.futures.ThreadPoolExecutor(max_workers=perspective_count) as executor:
            exec_begin = time.perf_counter()
            futures_to_call_configs = {executor.submit(self.thread_call, call_config): call_config for call_config in
                                       async_calls_to_issue}
            for future in concurrent.futures.as_completed(futures_to_call_configs):
                call_configuration = futures_to_call_configs[future]
                perspective = call_configuration.perspective
                check_type = call_configuration.check_type
                now = time.perf_counter()
                print(
                    f"Unpacking future result for {perspective} at time {str(datetime.now())}: {now - exec_begin:.2f} \
                    seconds from beginning")
                try:
                    data = future.result()
                except Exception as e:
                    stacktrace = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
                    print(f'{perspective} generated an exception: {stacktrace}')
                else:
                    if check_type not in perspective_responses_per_check_type:
                        perspective_responses_per_check_type[check_type] = []
                    try:
                        perspective_response = json.loads(data['Payload'].read().decode('utf-8'))
                        print(perspective_response)
                        perspective_response_body = json.loads(perspective_response['body'])
                        # deserialize perspective body to have a nested object in the output rather than a string
                        check_response = self.check_response_adapter.validate_python(perspective_response_body)
                        validity_per_perspective_per_check_type[check_type][perspective] |= check_response.check_passed
                        # TODO make sure responses per perspective match API spec...
                        perspective_responses_per_check_type[check_type].append(check_response)
                    except Exception:  # TODO what exceptions are we expecting here?
                        print(traceback.format_exc())
                        match check_type:
                            case CheckType.CAA:
                                check_error_response = CaaCheckResponse(
                                    perspective=perspective,
                                    check_passed=False,
                                    errors=[ValidationError(error_type=ErrorMessages.COORDINATOR_COMMUNICATION_ERROR.key,
                                                            error_message=ErrorMessages.COORDINATOR_COMMUNICATION_ERROR.message)],
                                    details=CaaCheckResponseDetails(caa_record_present=False),  # TODO Possibly should None to indicate the lookup failed.
                                    timestamp_ns=time.time_ns()
                                )
                            case CheckType.DCV:
                                check_error_response = DcvCheckResponse(
                                    perspective=perspective,
                                    check_passed=False,
                                    errors=[ValidationError(error_type=ErrorMessages.COORDINATOR_COMMUNICATION_ERROR.key,
                                                            error_message=ErrorMessages.COORDINATOR_COMMUNICATION_ERROR.message)],
                                    details=DcvCheckResponseDetails(),  # TODO what should go here in this case?
                                    timestamp_ns=time.time_ns()
                                )
                        validity_per_perspective_per_check_type[check_type][perspective] |= check_error_response.check_passed
                        perspective_responses_per_check_type[check_type].append(check_error_response)
        return perspective_responses_per_check_type, validity_per_perspective_per_check_type

    @staticmethod
    def create_perspective_cohorts(perspectives_per_rir: dict, cohort_size: int):
        if cohort_size == 1:
            return [[region] for region in chain.from_iterable(perspectives_per_rir.values())]  # TODO limit cohort number in this case?
        elif len(perspectives_per_rir.keys()) < 2:  # else if only one rir, can't meet requirements
            return []  # TODO throw an error? check this case in the validator?

        # the below is an upper bound for number of potential cohorts, assuming rir and distance rules can be met
        number_of_potential_cohorts = len(list(chain.from_iterable(perspectives_per_rir.values()))) // cohort_size
        new_cohorts, cohorts_with_two_rirs, full_cohorts = [], [], []
        for cohort_number in range(number_of_potential_cohorts):
            new_cohorts.append([])  # start with list of empty cohorts (list of lists)
        # get set of unique rirs from available_perspectives
        rirs_available = perspectives_per_rir.keys()
        # cycle through rirs in available_perspectives
        rirs_cycle = cycle(rirs_available)

        # first, try to fill up cohorts with 2 distinct rirs each
        while len(new_cohorts) > 0:  # remove cohorts from new_cohorts list when they have 2 rirs
            current_rir = next(rirs_cycle)
            cohort_index = 0
            while cohort_index < len(new_cohorts):  # looping like this to allow for removal of cohorts
                cohort = new_cohorts[cohort_index]
                assert len(cohort) <= 1  # should have at most 1 region in it at this point if we're here

                # if cohort already has this rir, then we were unable to distribute enough rirs to cover it
                # return its perspectives to the available list and remove it from new_cohorts
                if current_rir in [region.rir for region in cohort]:
                    for region in cohort:
                        perspectives_per_rir[region.rir].append(region)
                    del new_cohorts[cohort_index]
                    continue

                # if we are all out of perspectives for this rir, move on to the next rir
                if len(perspectives_per_rir[current_rir]) == 0:
                    break  # break out of cohort loop to get next rir

                # get the next perspective for the current rir
                perspective_to_add = perspectives_per_rir[current_rir].pop(0)
                cohort.append(perspective_to_add)

                # if cohort has 2 rirs, move it to cohorts_with_enough_rirs
                if len(cohort) == 2:
                    cohorts_with_two_rirs.append(new_cohorts.pop(cohort_index))
                else:
                    cohort_index += 1

        # now we have a list of cohorts with 2 rirs; time to distribute the rest of the perspectives
        # try to fill up one cohort at a time (seems like simpler logic) than trying to fill all cohorts at once
        while len(cohorts_with_two_rirs) > 0:
            too_close_perspectives = []
            cohort = cohorts_with_two_rirs[0]  # get the (next) cohort
            while len(cohort) < cohort_size and len(cohort) - cohort_size < len(list(chain.from_iterable(perspectives_per_rir.values()))):
                # get the next perspective for the current rir
                current_rir = next(rirs_cycle)

                # if we are all out of perspectives for this rir, move on to the next rir
                if len(perspectives_per_rir[current_rir]) == 0:
                    break  # break out of cohort loop to get next rir

                while len(perspectives_per_rir[current_rir]) > 0:
                    candidate_perspective = perspectives_per_rir[current_rir].pop(0)
                    if not any(candidate_perspective.is_perspective_too_close(perspective) for perspective in cohort):
                        cohort.append(candidate_perspective)
                        break
                    else:
                        too_close_perspectives.append(candidate_perspective)

            # if cohort is full, move it to full_cohorts
            if len(cohort) == cohort_size:
                full_cohorts.append(cohorts_with_two_rirs[0])
            else:  # otherwise, we ran out of perspectives to add to this cohort; it's a bad cohort so scrap it
                for perspective in cohort:
                    perspectives_per_rir[perspective.rir].append(perspective)
            del cohorts_with_two_rirs[0]
            # reset too_close_regions for next cohort
            for perspective in too_close_perspectives:
                perspectives_per_rir[perspective.rir].append(perspective)

        # now we have a list of full cohorts
        return full_cohorts

    @staticmethod
    def load_aws_region_config():
        """
        Reads in the available AWS regions from a configuration yaml and returns them as a list.
        :return: list of available AWS regions
        """
        with pkg_resources.open_text('resources', 'aws_region_config.yaml') as file:
            aws_region_config_yaml = yaml.safe_load(file)
            aws_region_type_adapter = TypeAdapter(list[RemotePerspective])
            aws_regions_list = aws_region_type_adapter.validate_python(aws_region_config_yaml['aws_available_regions'])
            aws_regions_dict = {region.code: region for region in aws_regions_list}
            return aws_regions_dict

    @staticmethod
    def build_400_response(error_name, issues_list):
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': error_name, 'validation_issues': issues_list})
        }

    @staticmethod
    def thread_call(call_config: RemoteCheckCallConfiguration):
        """
        Issues a call to a lambda function in a separate thread. This is a blocking call.
        This is purely AWS specific and should not be used in other contexts.
        :param call_config:
        :return:
        """
        print(f"Started lambda call for region {call_config.perspective} at {str(datetime.now())}")

        tic_init = time.perf_counter()
        client = boto3.client('lambda', call_config.perspective.split(".")[1])
        tic = time.perf_counter()
        response = client.invoke(  # AWS Lambda-specific structure
            FunctionName=call_config.lambda_arn,
            InvocationType='RequestResponse',
            Payload=json.dumps(call_config.input_args.model_dump())
        )
        toc = time.perf_counter()

        print(f"Response in region {call_config.perspective} took {toc - tic:0.4f} seconds to get response; \
              {tic - tic_init:.2f} seconds to start boto client; ended at {str(datetime.now())}\n")
        return response
