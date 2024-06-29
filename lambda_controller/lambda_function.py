import json
import boto3
import time
import concurrent.futures
from datetime import datetime
import os

# Load lists of perspective names, validator arns, and caa arns from environment vars.
perspective_name_list = os.environ['perspective_names'].split("|")
validator_arn_list = os.environ['validator_arns'].split("|")
caa_arn_list = os.environ['caa_arns'].split("|")


func_arns = {
    "validations": {perspective_name_list[i]: validator_arn_list[i] for i in range(len(perspective_name_list))},
    "caa": {perspective_name_list[i]: caa_arn_list[i] for i in range(len(perspective_name_list))}
}

VERSION = "0.1.0b"

def thread_call(lambda_arn, region, input_params):
    print(f'Started lambda call for region {region} at {str(datetime.now())}')
    
    tic_init = time.perf_counter()
    client = boto3.client('lambda', region.split(".")[1])
    tic = time.perf_counter()
    response = client.invoke(
        FunctionName = lambda_arn,      
        InvocationType = 'RequestResponse',
        Payload = json.dumps(input_params)
    )
    toc = time.perf_counter()
    
    print(f"Response in region {region} took {toc - tic:0.4f} seconds to get response; {tic - tic_init:.2f} seconds to start boto client; ended at {str(datetime.now())}\n")
    return response


def lambda_handler(event, context):
    request_path = event["path"]
    body = json.loads(event["body"])
    if "regions" in body:
        regions = body["regions"]
    else:
        regions = perspective_name_list
    quorum_count = body["quorum-count"]
    
    async_calls_to_invoke = []

    match request_path:
        case '/caa-lookup':
            input_args = {"identifier": body["identifier"],
                          "caa-params": body["caa-params"]}
            for region in regions:
                arn = func_arns['caa'][region]
                async_calls_to_invoke.append(("caa", region, arn, input_args))
        case '/validation':
            region_arns = func_arns['validations']
            input_args = {"identifier": body["identifier"],
                           "validation-method": body["validation-method"],
                           "validation-params": body["validation-params"]}
            for region in regions:
                arn = func_arns['validations'][region]
                async_calls_to_invoke.append(("validation", region, arn, input_args))
        case '/validation-with-caa-lookup':
            for region in regions:
                async_calls_to_invoke.append(("caa", region, func_arns['caa'][region], 
                                              {"identifier": body["identifier"],
                                               "caa-params": body["caa-params"]}))
                async_calls_to_invoke.append(("validation", region, func_arns['validations'][region],
                                             {"identifier": body["identifier"],
                                              "validation-method": body["validation-method"],
                                              "validation-params": body["validation-params"]}))
    
    
    num_perspectives = len(regions)
    perspective_responses = {}
    valid_by_perspective = {r: False for r in regions}
    
    # example code: https://docs.python.org/3/library/concurrent.futures.html
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_perspectives) as executor:
        exec_begin = time.perf_counter()
        future_to_dv = {executor.submit(thread_call, arn, region, args): (region, optype) for (optype, region, arn, args) in async_calls_to_invoke}
        for future in concurrent.futures.as_completed(future_to_dv):
            region, optype = future_to_dv[future]
            now = time.perf_counter()
            print(f'Unpacking future result for {region} at time {str(datetime.now())}: {now - exec_begin:.2f} seconds from beginning')
            try:
                data = future.result()
            except Exception as exc:
                print(f'{region} generated an exception: {exc}')
            else:
                persp_resp = json.loads(data['Payload'].read().decode('utf-8'))
                persp_resp_body = json.loads(persp_resp['body'])
                if persp_resp_body['ValidForIssue']:
                    print(f'Perspective in {persp_resp_body["Region"]} was valid!')
                valid_by_perspective[region] |= persp_resp_body['ValidForIssue']
                if optype not in perspective_responses:
                    perspective_responses[optype] = []
                perspective_responses[optype].append(persp_resp)

    valid_perspective_count = sum(valid_by_perspective.values())
    print(f"overall OK to issue? {valid_perspective_count >= quorum_count} num valid VPs: {valid_perspective_count} num to meet quorum: {quorum_count}" )
    
    resp_body = {
        "api-version": VERSION,
        "is-valid": (valid_perspective_count >= quorum_count),
        "mpic-params": {
            "perspective-count": len(regions),
            "quorum-count": quorum_count
        },
        "perspectives": perspective_responses
    }

    return {
        'statusCode': 200,
        'body': json.dumps(resp_body)
    }
