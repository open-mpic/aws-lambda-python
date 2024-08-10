import json
from typing import Final
import boto3
import time
import concurrent.futures
from datetime import datetime
import os
import random
import hashlib

from aws_lambda_python.mpic_coordinator.domain.check_type import CheckType
from aws_lambda_python.mpic_coordinator.domain.remote_check_call_configuration import RemoteCheckCallConfiguration
from aws_lambda_python.mpic_coordinator.domain.request_paths import RequestPaths
from aws_lambda_python.mpic_coordinator.messages.validation_messages import ValidationMessages
from aws_lambda_python.mpic_coordinator.mpic_request_validator import MpicRequestValidator

VERSION: Final[str] = '1.0.0'  # TODO do we need to externalize this? it's a bit hidden here


class MpicCoordinator:
    def __init__(self):
        # Load lists of perspective names, validator arns, and caa arns from environment vars.
        self.known_perspectives = os.environ['perspective_names'].split("|")
        self.validator_arn_list = os.environ['validator_arns'].split("|")
        self.caa_arn_list = os.environ['caa_arns'].split("|")
        self.default_perspective_count = int(os.environ['default_perspective_count'])
        self.default_quorum = int(os.environ['default_quorum'])
        self.enforce_distinct_rir_regions = int(os.environ['enforce_distinct_rir_regions']) == 1
        self.hash_secret = os.environ['hash_secret']

        # Create a dictionary of ARNs per check type per perspective to simplify lookup in the future.
        # (Assumes known_perspectives list, validator_arn_list, and caa_arn_list are the same length.)
        self.arns_per_check = {
            CheckType.DCV: {self.known_perspectives[i]: self.validator_arn_list[i] for i in range(len(self.known_perspectives))},
            CheckType.CAA: {self.known_perspectives[i]: self.caa_arn_list[i] for i in range(len(self.known_perspectives))}
        }

    @staticmethod
    def thread_call(call_config: RemoteCheckCallConfiguration):
        print(f"Started lambda call for region {call_config.perspective} at {str(datetime.now())}")

        tic_init = time.perf_counter()
        client = boto3.client('lambda', call_config.perspective.split(".")[1])
        tic = time.perf_counter()
        response = client.invoke(
            FunctionName=call_config.lambda_arn,
            InvocationType='RequestResponse',
            Payload=json.dumps(call_config.args)
        )
        toc = time.perf_counter()

        print(f"Response in region {call_config.perspective} took {toc - tic:0.4f} seconds to get response; \
              {tic - tic_init:.2f} seconds to start boto client; ended at {str(datetime.now())}\n")
        return response

    # Returns a random subset of perspectives with a goal of maximum RIR diversity to increase diversity.
    # Perspectives must be of the form 'RIR.AWS-region'.
    def random_select_perspectives_considering_rir(self, available_perspectives, count, domain_or_ip_target):
        if count > len(available_perspectives):
            raise ValueError(
                f"Count ({count}) must be <= the number of available perspectives ({available_perspectives})")

        # Compute the distinct list or RIRs from all perspectives being considered.
        rirs_available = list(set([perspective.split('.')[0] for perspective in available_perspectives]))

        # Seed the random generator with the hash secret concatenated with the identifier in all lowercase.
        # This prevents the adversary from gaining an advantage by retrying and getting different vantage point sets.
        # (An alternative would be to limit retries per identifier, which has its own pros/cons.)
        random.seed(hashlib.sha256((self.hash_secret + domain_or_ip_target.lower()).encode('ASCII')).digest())

        # Get a random ordering of RIRs
        random.shuffle(rirs_available)

        # Create a list of the list of each perspective included in a specific RIR.
        perspectives_in_each_rir = [
            [perspective for perspective in available_perspectives if perspective.split('.')[0] == rir]
            for rir in rirs_available]

        # Chosen perspectives is populated with a random sample for each RIR until count is met.
        chosen_perspectives = []

        # RIR index loops through the different RIRs and adds a single chosen perspective from each RIR on each iteration.
        rir_index = 0
        while len(chosen_perspectives) < count:
            if len(perspectives_in_each_rir[rir_index]) >= 1:
                perspective_chosen = random.choice(perspectives_in_each_rir[rir_index])
                chosen_perspectives.append(perspective_chosen)
                perspectives_in_each_rir[rir_index].remove(perspective_chosen)
            rir_index += 1
            rir_index %= len(rirs_available)
        return chosen_perspectives

    def coordinate_mpic(self, event):
        request_path = event['path']
        body = json.loads(event['body'])

        # TODO validate the request path?

        is_request_body_valid, validation_issues = MpicRequestValidator.is_request_body_valid(request_path, body,
                                                                                              self.known_perspectives)
        if not is_request_body_valid:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': ValidationMessages.REQUEST_VALIDATION_FAILED.key,
                                    'validation-issues': [issue.__dict__ for issue in validation_issues]})
            }

        # Extract the system params object.
        system_params = body['system-params']

        # Extract the target identifier (domain name or IP for which control is being validated) TODO rename this field
        domain_or_ip_target = system_params['identifier']

        # Determine the perspectives and perspective count to use for this request.
        perspective_count = self.default_perspective_count
        if 'perspectives' in system_params:
            perspectives_to_use = system_params['perspectives']
            perspective_count = len(perspectives_to_use)
        else:
            if 'perspective-count' in system_params:
                perspective_count = system_params['perspective-count']
            perspectives_to_use = self.random_select_perspectives_considering_rir(self.known_perspectives,
                                                                                  perspective_count,
                                                                                  domain_or_ip_target)

        # FIXME default_quorum should follow BRs -- if perspectives <=5, quorum is perspectives-1, else perspectives-2
        # otherwise could have, for example, 10 perspectives and default quorum of 5 which is too low
        quorum_count = self.default_quorum
        if 'quorum-count' in system_params:
            quorum_count = system_params['quorum-count']

        # Collect async calls to invoke for each perspective.
        async_calls_to_issue = self.collect_async_calls_to_issue(request_path, body, perspectives_to_use)

        perspective_responses_per_check_type, validity_per_perspective_per_check_type = (
            self.issue_async_calls_and_collect_responses(perspectives_to_use, async_calls_to_issue))

        valid_by_check_type = {}
        two_rir_regions_by_check_type = {}
        for check_type in [CheckType.CAA, CheckType.DCV]:
            valid_perspective_count = sum(validity_per_perspective_per_check_type[check_type].values())

            # Create a list of valid perspectives.
            valid_perspectives = [perspective for perspective in validity_per_perspective_per_check_type[check_type] if
                                  validity_per_perspective_per_check_type[check_type][perspective]]

            # Create a list of RIRs that have a valid perspective.
            valid_rirs = [perspective.split(".")[0] for perspective in valid_perspectives]

            distinct_valid_rirs = set(valid_rirs)
            print(len(distinct_valid_rirs))
            two_rir_regions_by_check_type[check_type] = len(distinct_valid_rirs) >= 2

            # TODO optionally enforce 2 distinct RIR policy.

            valid_by_check_type[check_type] = valid_perspective_count >= quorum_count

        # TODO update API -- required-quorum-count is not there today and probably should be if it's dynamically derived
        resp_body = {
            'api-version': VERSION,
            'request-system-params': system_params,  # TODO rename this field in API
            'number-of-perspectives-used': perspective_count,  # TODO add this field to API
            'required-quorum-count-used': quorum_count,  # TODO add this field to API
        }
        # TODO add number of retries once retry logic is in place

        match request_path:
            case RequestPaths.CAA_CHECK:
                resp_body['perspectives'] = perspective_responses_per_check_type[CheckType.CAA]
                resp_body['is-valid'] = valid_by_check_type[CheckType.CAA] and (
                        not self.enforce_distinct_rir_regions or two_rir_regions_by_check_type[CheckType.CAA])
            case RequestPaths.DCV_CHECK:
                resp_body['perspectives'] = perspective_responses_per_check_type[CheckType.DCV]
                resp_body['validation-details'] = body['validation-details']
                resp_body['validation-method'] = body['validation-method']
                resp_body['is-valid'] = valid_by_check_type[CheckType.DCV] and (
                        not self.enforce_distinct_rir_regions or two_rir_regions_by_check_type[CheckType.DCV])
            case RequestPaths.DCV_WITH_CAA_CHECK:
                resp_body['perspectives-validation'] = perspective_responses_per_check_type['validation']
                resp_body['perspectives-caa'] = perspective_responses_per_check_type['caa']
                resp_body['validation-details'] = body['validation-details']
                resp_body['validation-method'] = body['validation-method']
                resp_body['is-valid-validation'] = valid_by_check_type[CheckType.DCV] and (
                        not self.enforce_distinct_rir_regions or two_rir_regions_by_check_type[CheckType.DCV])
                resp_body['is-valid-caa'] = valid_by_check_type[CheckType.CAA] and (
                        not self.enforce_distinct_rir_regions or two_rir_regions_by_check_type[CheckType.CAA])
                resp_body['is-valid'] = resp_body['is-valid-validation'] and resp_body['is-valid-caa']

        return {
            'statusCode': 200,
            'body': json.dumps(resp_body)
        }

    def collect_async_calls_to_issue(self, request_path, body, perspectives_to_use) -> list[RemoteCheckCallConfiguration]:
        domain_or_ip_target = body['system-params'][
            'identifier']  # should have already checked for validity by this point
        async_calls_to_issue = []

        # TODO are validation-method and validation-details required but caa-details NOT required?

        if request_path in (RequestPaths.CAA_CHECK, RequestPaths.DCV_WITH_CAA_CHECK):
            input_args = {'identifier': domain_or_ip_target,
                          'caa-params': body['caa-details'] if 'caa-details' in body else {}}
            for perspective in perspectives_to_use:
                arn = self.arns_per_check[CheckType.CAA][perspective]
                call_config = RemoteCheckCallConfiguration(CheckType.CAA, perspective, arn, input_args)
                async_calls_to_issue.append(call_config)

        if request_path in (RequestPaths.DCV_CHECK, RequestPaths.DCV_WITH_CAA_CHECK):
            perspective_arns = self.arns_per_check[CheckType.DCV]
            input_args = {'identifier': domain_or_ip_target,
                          'validation-method': body['validation-method'],
                          'validation-params': body['validation-details']}
            for perspective in perspectives_to_use:
                arn = perspective_arns[perspective]
                call_config = RemoteCheckCallConfiguration(CheckType.DCV, perspective, arn, input_args)
                async_calls_to_issue.append(call_config)

        return async_calls_to_issue

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
                    print(f'{perspective} generated an exception: {e}')
                else:
                    perspective_response = json.loads(data['Payload'].read().decode('utf-8'))
                    print(perspective_response)  # Debugging
                    perspective_response_body = json.loads(perspective_response['body'])
                    if perspective_response_body['ValidForIssue']:
                        print(f"Perspective in {perspective_response_body['Region']} was valid!")
                    validity_per_perspective_per_check_type[check_type][perspective] |= perspective_response_body[
                        'ValidForIssue']
                    if check_type not in perspective_responses_per_check_type:
                        perspective_responses_per_check_type[check_type] = []
                    perspective_responses_per_check_type[check_type].append(perspective_response)
        return perspective_responses_per_check_type, validity_per_perspective_per_check_type
