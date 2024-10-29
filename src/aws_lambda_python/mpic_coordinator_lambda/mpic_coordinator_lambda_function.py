from aws_lambda_python.mpic_coordinator.mpic_coordinator import MpicCoordinator, MpicCoordinatorConfiguration
from aws_lambda_python.mpic_coordinator.messages.mpic_request_validation_messages import MpicRequestValidationMessages
from aws_lambda_python.mpic_coordinator.domain.remote_check_call_configuration import RemoteCheckCallConfiguration
from aws_lambda_python.common_domain.enum.check_type import CheckType
from aws_lambda_python.mpic_coordinator.domain.enum.request_path import RequestPath
from aws_lambda_python.common_domain.remote_perspective import RemotePerspective

import boto3
import os
import json

known_perspectives = os.environ['perspective_names'].split("|")
dcv_arn_list = os.environ['validator_arns'].split("|")  # TODO rename to dcv_arns
caa_arn_list = os.environ['caa_arns'].split("|")
default_perspective_count = int(os.environ['default_perspective_count'])
enforce_distinct_rir_regions = int(os.environ['enforce_distinct_rir_regions']) == 1  # TODO may not need...
global_max_attempts = int(os.environ['absolute_max_attempts']) if 'absolute_max_attempts' in os.environ else None
hash_secret = os.environ['hash_secret']


arns_per_perspective_per_check_type = {
            CheckType.DCV: {known_perspectives[i]: dcv_arn_list[i] for i in range(len(known_perspectives))},
            CheckType.CAA: {known_perspectives[i]: caa_arn_list[i] for i in range(len(known_perspectives))}
        }

mpic_coordinator_configuration = MpicCoordinatorConfiguration(
        known_perspectives, 
        default_perspective_count, 
        enforce_distinct_rir_regions, 
        global_max_attempts, 
        hash_secret)


# This function is a "dumb" transport for serialized data to a remote perspective and a serialized response from the remote perspective. MPIC Coordinator is tasked with ensuring the data from this function is sane. This function may raise an exception if something goes wrong.
def call_remote_perspective(perspective: RemotePerspective, check_type: CheckType, check_request_serialized: str):
    # Uses dcv_arn_list, caa_arn_list
    client = boto3.client('lambda', perspective.code)
    function_name = arns_per_perspective_per_check_type[check_type][perspective.to_rir_code()]
    response = client.invoke(  # AWS Lambda-specific structure
            FunctionName=function_name,
            InvocationType='RequestResponse',
            Payload=check_request_serialized
        )
    response_payload = json.loads(response['Payload'].read().decode('utf-8'))

    return response_payload['body']


coordinator = MpicCoordinator(call_remote_perspective, mpic_coordinator_configuration)


# noinspection PyUnusedLocal
# for now, we are not using context, but it is required by the lambda handler signature
def lambda_handler(event, context):
    request_path = event['path']
    if request_path not in iter(RequestPath):
        return MpicCoordinator.build_400_response(MpicRequestValidationMessages.REQUEST_VALIDATION_FAILED.key,
            [MpicRequestValidationMessages.UNSUPPORTED_REQUEST_PATH.key])
    
    return coordinator.coordinate_mpic(event['body'])
