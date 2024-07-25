import json
import boto3
import time
import concurrent.futures
from datetime import datetime
import os
import random

VERSION = "1.0.0"


class MpicOrchestrator:
    def __init__(self):
        # Load lists of perspective names, validator arns, and caa arns from environment vars.
        self.perspective_name_list = os.environ['perspective_names'].split("|")
        self.validator_arn_list = os.environ['validator_arns'].split("|")
        self.caa_arn_list = os.environ['caa_arns'].split("|")
        self.default_perspective_count = int(os.environ['default_perspective_count'])
        self.default_quorum = int(os.environ['default_quorum'])
        self.enforce_distinct_rir_regions = int(os.environ['enforce_distinct_rir_regions']) == 1

        self.func_arns = {
            "validations": {self.perspective_name_list[i]: self.validator_arn_list[i] for i in
                            range(len(self.perspective_name_list))},
            "caa": {self.perspective_name_list[i]: self.caa_arn_list[i] for i in range(len(self.perspective_name_list))}
        }

    @staticmethod
    def thread_call(lambda_arn, region, input_params):
        print(f'Started lambda call for region {region} at {str(datetime.now())}')

        tic_init = time.perf_counter()
        client = boto3.client('lambda', region.split(".")[1])
        tic = time.perf_counter()
        response = client.invoke(
            FunctionName=lambda_arn,
            InvocationType='RequestResponse',
            Payload=json.dumps(input_params)
        )
        toc = time.perf_counter()

        print(f"Response in region {region} took {toc - tic:0.4f} seconds to get response; {tic - tic_init:.2f} \
                seconds to start boto client; ended at {str(datetime.now())}\n")
        return response

    # Returns a random subset of perspectives with a goal of maximum RIR diversity to increase diversity.
    # Perspectives must be of the form 'RIR.AWS-region'.
    @staticmethod
    def random_select_perspectives_considering_rir(available_perspectives, count):
        if count > len(available_perspectives):
            raise ValueError(
                f"Count ({count}) must be <= the number of available perspectives ({available_perspectives})")

        # Compute the distinct list or RIRs from all perspectives being considered.
        rirs_available = list(set([perspective.split('.')[0] for perspective in available_perspectives]))

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

    def orchestrate_mpic(self, event):
        request_path = event["path"]
        body = json.loads(event["body"])

        # Begin with an API version check.
        request_api_version_split = body['api-version'].split('.')
        if int(request_api_version_split[0]) != 1 or int(request_api_version_split[1]) > 0:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'api-version-mismatch', 'error-msg': f"Sent API Version\
                        {body['api-version']} is not compatible with system API version {VERSION}."})
            }

        # Extract the system params object.
        system_params = body['system-params']

        # Extract the identifier.
        identifier = system_params['identifier']

        regions = MpicOrchestrator.random_select_perspectives_considering_rir(self.perspective_name_list,
                                                                              self.default_perspective_count)
        if 'perspectives' in system_params and 'perspective-count' in system_params:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'perspectives-and-perspective-count', 'error-msg': f"Perspectives cannot\
                                   be specified along with perspective count. Use one parameter or the other."})
            }
        elif 'perspectives' in system_params:
            regions = system_params['perspectives']
        elif 'perspective-count' in system_params:
            regions = self.random_select_perspectives_considering_rir(self.perspective_name_list,
                                                                      system_params['perspective-count'])

        quorum_count = self.default_quorum
        if 'quorum-count' in system_params:
            quorum_count = system_params['quorum-count']

        async_calls_to_invoke = []
        print(body)
        match request_path:
            case '/caa-lookup':
                input_args = {"identifier": identifier,
                              "caa-params": body['caa-details'] if 'caa-details' in body else {}}
                for region in regions:
                    arn = self.func_arns['caa'][region]
                    async_calls_to_invoke.append(("caa", region, arn, input_args))
            case '/validation':
                region_arns = self.func_arns['validations']
                input_args = {'identifier': identifier,
                              'validation-method': body['validation-method'],
                              'validation-params': body['validation-details']}
                for region in regions:
                    arn = region_arns[region]
                    async_calls_to_invoke.append(("validation", region, arn, input_args))
            case '/validation-with-caa-lookup':
                for region in regions:
                    async_calls_to_invoke.append(("caa", region, self.func_arns['caa'][region],
                                                  {'identifier': identifier,
                                                   'caa-params': body['caa-details'] if 'caa-details' in body else {}}))
                    async_calls_to_invoke.append(("validation", region, self.func_arns['validations'][region],
                                                  {'identifier': identifier,
                                                   'validation-method': body['validation-method'],
                                                   'validation-params': body['validation-details']}))

        num_perspectives = len(regions)
        perspective_responses = {}
        valid_by_perspective_by_op_type = {'validation': {r: False for r in regions},
                                           'caa': {r: False for r in regions}}

        # example code: https://docs.python.org/3/library/concurrent.futures.html
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_perspectives) as executor:
            exec_begin = time.perf_counter()
            future_to_dv = {executor.submit(self.thread_call, arn, region, args): (region, optype) for
                            (optype, region, arn, args) in async_calls_to_invoke}
            for future in concurrent.futures.as_completed(future_to_dv):
                region, optype = future_to_dv[future]
                now = time.perf_counter()
                print(
                    f'Unpacking future result for {region} at time {str(datetime.now())}: {now - exec_begin:.2f} \
                    seconds from beginning')
                try:
                    data = future.result()
                except Exception as exc:
                    print(f'{region} generated an exception: {exc}')
                else:
                    persp_resp = json.loads(data['Payload'].read().decode('utf-8'))
                    persp_resp_body = json.loads(persp_resp['body'])
                    if persp_resp_body['ValidForIssue']:
                        print(f'Perspective in {persp_resp_body["Region"]} was valid!')
                    valid_by_perspective_by_op_type[optype][region] |= persp_resp_body['ValidForIssue']
                    if optype not in perspective_responses:
                        perspective_responses[optype] = []
                    perspective_responses[optype].append(persp_resp)

        valid_by_op_type = {}
        two_rir_regions_by_op_type = {}
        for optype in ['validation', 'caa']:
            valid_perspective_count = sum(valid_by_perspective_by_op_type[optype].values())

            # Create a list of valid perspectives.
            valid_perspectives = [perspective for perspective in valid_by_perspective_by_op_type[optype] if
                                  valid_by_perspective_by_op_type[optype][perspective]]

            # Create a list of RIRs that have a valid perspective.
            valid_rirs = [perspective.split(".")[0] for perspective in valid_perspectives]

            distinct_valid_rirs = set(valid_rirs)
            print(len(distinct_valid_rirs))
            two_rir_regions_by_op_type[optype] = len(distinct_valid_rirs) >= 2

            # Todo: optionally enforce 2 distinct RIR policy.
            print(
                f"overall OK to issue for {optype}? {valid_perspective_count >= quorum_count} num valid VPs: {valid_perspective_count} num to meet quorum: {quorum_count}")
            valid_by_op_type[optype] = valid_perspective_count >= quorum_count

        resp_body = {
            "api-version": VERSION,
            "system-params": system_params
        }

        match request_path:
            case '/caa-lookup':
                resp_body['perspectives'] = perspective_responses['caa']
                resp_body['is-valid'] = valid_by_op_type['caa'] and (
                        not self.enforce_distinct_rir_regions or two_rir_regions_by_op_type['caa'])
            case '/validation':
                resp_body['perspectives'] = perspective_responses['validation']
                resp_body['validation-details'] = body['validation-details']
                resp_body['validation-method'] = body['validation-method']
                resp_body['is-valid'] = valid_by_op_type['validation'] and (
                        not self.enforce_distinct_rir_regions or two_rir_regions_by_op_type['validation'])
            case '/validation-with-caa-lookup':
                resp_body['perspectives-validation'] = perspective_responses['validation']
                resp_body['perspectives-caa'] = perspective_responses['caa']
                resp_body['validation-details'] = body['validation-details']
                resp_body['validation-method'] = body['validation-method']
                resp_body['is-valid-validation'] = valid_by_op_type['validation'] and (
                        not self.enforce_distinct_rir_regions or two_rir_regions_by_op_type['validation'])
                resp_body['is-valid-caa'] = valid_by_op_type['caa'] and (
                        not self.enforce_distinct_rir_regions or two_rir_regions_by_op_type['caa'])
                resp_body['is-valid'] = resp_body['is-valid-validation'] and resp_body['is-valid-caa']

        return {
            'statusCode': 200,
            'body': json.dumps(resp_body)
        }


def lambda_handler(event):
    mpic_orchestrator = MpicOrchestrator()
    return mpic_orchestrator.orchestrate_mpic(event)
