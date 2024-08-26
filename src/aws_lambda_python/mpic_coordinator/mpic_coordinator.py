import json
import traceback
from typing import Final
import boto3
import time
import concurrent.futures
from datetime import datetime
import os
import random
import hashlib

import pydantic
from aws_lambda_python.common_domain.check_response import BaseCheckResponse
from aws_lambda_python.common_domain.check_request import CaaCheckRequest
from aws_lambda_python.common_domain.check_request import DcvCheckRequest
from aws_lambda_python.mpic_coordinator.domain.enum.check_type import CheckType
from aws_lambda_python.mpic_coordinator.domain.mpic_request import MpicCaaRequest
from aws_lambda_python.mpic_coordinator.domain.mpic_request import MpicDcvRequest
from aws_lambda_python.mpic_coordinator.domain.mpic_request import MpicDcvWithCaaRequest
from aws_lambda_python.mpic_coordinator.domain.remote_check_call_configuration import RemoteCheckCallConfiguration
from aws_lambda_python.mpic_coordinator.domain.request_path import RequestPath
from aws_lambda_python.mpic_coordinator.messages.validation_messages import ValidationMessages
from aws_lambda_python.mpic_coordinator.mpic_request_validator import MpicRequestValidator
from aws_lambda_python.mpic_coordinator.mpic_response_builder import MpicResponseBuilder

VERSION: Final[str] = '1.0.0'  # TODO do we need to externalize this? it's a bit hidden here


class MpicCoordinator:
    def __init__(self):
        # Load lists of perspective names, validator arns, and caa arns from environment vars.
        self.known_perspectives = os.environ['perspective_names'].split("|")
        self.validator_arn_list = os.environ['validator_arns'].split("|")
        self.caa_arn_list = os.environ['caa_arns'].split("|")
        self.default_perspective_count = int(os.environ['default_perspective_count'])
        self.enforce_distinct_rir_regions = int(os.environ['enforce_distinct_rir_regions']) == 1
        self.hash_secret = os.environ['hash_secret']

        # Create a dictionary of ARNs per check type per perspective to simplify lookup in the future.
        # (Assumes known_perspectives list, validator_arn_list, and caa_arn_list are the same length.)
        self.arns_per_perspective_per_check_type = {
            CheckType.DCV: {self.known_perspectives[i]: self.validator_arn_list[i] for i in range(len(self.known_perspectives))},
            CheckType.CAA: {self.known_perspectives[i]: self.caa_arn_list[i] for i in range(len(self.known_perspectives))}
        }

    def coordinate_mpic(self, event):
        request_path = event['path']

        # parse event body into mpic_request
        try:
            match request_path:
                case RequestPath.CAA_CHECK:
                    mpic_request = MpicCaaRequest.model_validate_json(event['body'])
                case RequestPath.DCV_CHECK:
                    mpic_request = MpicDcvRequest.model_validate_json(event['body'])
                case RequestPath.DCV_WITH_CAA_CHECK:
                    mpic_request = MpicDcvWithCaaRequest.model_validate_json(event['body'])
                case _:
                    return {
                        'statusCode': 400,  # must be snakeCase for well-formed AWS Lambda response
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({'error': ValidationMessages.REQUEST_VALIDATION_FAILED.key,
                                            'validation_issues': [ValidationMessages.UNSUPPORTED_REQUEST_PATH.key]})
                    }
        except pydantic.ValidationError as validation_error:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': ValidationMessages.REQUEST_VALIDATION_FAILED.key,
                                    'validation_issues': validation_error.errors()})
            }

        is_request_valid, validation_issues = MpicRequestValidator.is_request_valid(request_path, mpic_request, self.known_perspectives)

        if not is_request_valid:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': ValidationMessages.REQUEST_VALIDATION_FAILED.key,
                                    'validation_issues': [vars(issue) for issue in validation_issues]})
            }

        system_params = mpic_request.orchestration_parameters

        # Determine the perspectives and perspective count to use for this request.
        perspective_count = self.default_perspective_count
        if system_params.perspectives is not None:
            perspectives_to_use = system_params.perspectives
            perspective_count = len(perspectives_to_use)
        else:
            if system_params.perspective_count is not None:
                perspective_count = system_params.perspective_count
            perspectives_to_use = self.select_random_perspectives_across_rirs(self.known_perspectives,
                                                                              perspective_count,
                                                                              system_params.domain_or_ip_target)

        quorum_count = self.determine_required_quorum_count(system_params, perspective_count)

        # Collect async calls to invoke for each perspective.
        async_calls_to_issue = self.collect_async_calls_to_issue(request_path, mpic_request, perspectives_to_use)

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
    def select_random_perspectives_across_rirs(self, available_perspectives, count, domain_or_ip_target):
        if count > len(available_perspectives):
            raise ValueError(
                f"Count ({count}) must be <= the number of available perspectives ({available_perspectives})")

        # Compute the distinct list or RIRs from all perspectives being considered.
        rirs_available = list(set([perspective.split('.')[0] for perspective in available_perspectives]))

        # TODO implement perspective cohort selection logic for floor(perspectives/count) > 1
        # Seed the random generator with the hash secret concatenated with the domain-or-ip-target in all lowercase.
        # This prevents the adversary from gaining an advantage by retrying and getting different vantage point sets.
        # (An alternative would be to limit retries per domain-or-ip-target, which has its own pros/cons.)
        random.seed(hashlib.sha256((self.hash_secret + domain_or_ip_target.lower()).encode('ASCII')).digest())

        # Get a random ordering of RIRs
        random.shuffle(rirs_available)

        # Create a list of lists, grouping perspectives by their RIR.
        perspectives_in_each_rir = [
            [perspective for perspective in available_perspectives if perspective.split('.')[0] == rir]
            for rir in rirs_available
        ]

        # RIR index loops through the different RIRs and adds a single chosen perspective from each RIR on each iteration.
        chosen_perspectives = []
        rir_index = 0
        while len(chosen_perspectives) < count:
            if len(perspectives_in_each_rir[rir_index]) >= 1:
                perspective_chosen = random.choice(perspectives_in_each_rir[rir_index])
                chosen_perspectives.append(perspective_chosen)
                perspectives_in_each_rir[rir_index].remove(perspective_chosen)
            rir_index += 1
            rir_index %= len(rirs_available)
        return chosen_perspectives

    # Determines the minimum required quorum size if none is specified in the request.
    @staticmethod
    def determine_required_quorum_count(system_params, perspective_count):
        if system_params.quorum_count is not None:
            required_quorum_count = system_params.quorum_count
        else:
            required_quorum_count = perspective_count - 1 if perspective_count <= 5 else perspective_count - 2
        return required_quorum_count

    # Configures the async lambda function calls to issue for the check request.
    def collect_async_calls_to_issue(self, request_path, mpic_request, perspectives_to_use) -> list[RemoteCheckCallConfiguration]:
        domain_or_ip_target = mpic_request.orchestration_parameters.domain_or_ip_target
        async_calls_to_issue = []

        if request_path in (RequestPath.CAA_CHECK, RequestPath.DCV_WITH_CAA_CHECK):
            check_parameters = CaaCheckRequest(domain_or_ip_target=domain_or_ip_target, caa_details=mpic_request.caa_details)
            for perspective in perspectives_to_use:
                arn = self.arns_per_perspective_per_check_type[CheckType.CAA][perspective]
                call_config = RemoteCheckCallConfiguration(CheckType.CAA, perspective, arn, check_parameters)
                async_calls_to_issue.append(call_config)

        if request_path in (RequestPath.DCV_CHECK, RequestPath.DCV_WITH_CAA_CHECK):
            check_parameters = DcvCheckRequest(domain_or_ip_target=domain_or_ip_target, dcv_details=mpic_request.dcv_details)
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
                    perspective_response = json.loads(data['Payload'].read().decode('utf-8'))
                    perspective_response_body = json.loads(perspective_response['body'])
                    # deserialize perspective body to have a nested object in the output rather than a string
                    perspective_response['body'] = perspective_response_body
                    check_response = BaseCheckResponse.model_validate(perspective_response_body)
                    validity_per_perspective_per_check_type[check_type][perspective] |= check_response.valid_for_issuance
                    if check_type not in perspective_responses_per_check_type:
                        perspective_responses_per_check_type[check_type] = []
                    # TODO make sure responses per perspective match API spec...
                    perspective_responses_per_check_type[check_type].append(perspective_response)
        return perspective_responses_per_check_type, validity_per_perspective_per_check_type

    @staticmethod
    def thread_call(call_config: RemoteCheckCallConfiguration):
        print(f"Started lambda call for region {call_config.perspective} at {str(datetime.now())}")

        tic_init = time.perf_counter()
        client = boto3.client('lambda', call_config.perspective.split(".")[1])
        tic = time.perf_counter()
        response = client.invoke(
            FunctionName=call_config.lambda_arn,
            InvocationType='RequestResponse',
            Payload=json.dumps(call_config.input_args.model_dump())
        )
        toc = time.perf_counter()

        print(f"Response in region {call_config.perspective} took {toc - tic:0.4f} seconds to get response; \
              {tic - tic_init:.2f} seconds to start boto client; ended at {str(datetime.now())}\n")
        return response
