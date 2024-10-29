from aws_lambda_python.mpic_coordinator.mpic_coordinator import MpicCoordinator, MpicCoordinatorConfiguration
from aws_lambda_python.mpic_coordinator.messages.mpic_request_validation_messages import MpicRequestValidationMessages
from aws_lambda_python.common_domain.enum.check_type import CheckType
from aws_lambda_python.mpic_coordinator.domain.enum.request_path import RequestPath
from aws_lambda_python.common_domain.remote_perspective import RemotePerspective

import boto3
import os
import json


class MpicCoordinatorLambdaHandler:
    def __init__(self):
        self._initialize_handler()

    def _initialize_handler(self):
        # load environment variables
        self.known_perspectives = os.environ['perspective_names'].split("|")
        self.dcv_arn_list = os.environ['validator_arns'].split("|")  # TODO rename to dcv_arns
        self.caa_arn_list = os.environ['caa_arns'].split("|")
        self.default_perspective_count = int(os.environ['default_perspective_count'])
        self.enforce_distinct_rir_regions = int(os.environ['enforce_distinct_rir_regions']) == 1  # TODO may not need...
        self.global_max_attempts = int(os.environ['absolute_max_attempts']) if 'absolute_max_attempts' in os.environ else None
        self.hash_secret = os.environ['hash_secret']

        self.arns_per_perspective_per_check_type = {
            CheckType.DCV: {self.known_perspectives[i]: self.dcv_arn_list[i] for i in range(len(self.known_perspectives))},
            CheckType.CAA: {self.known_perspectives[i]: self.caa_arn_list[i] for i in range(len(self.known_perspectives))}
        }

        self.mpic_coordinator_configuration = MpicCoordinatorConfiguration(
            self.known_perspectives,
            self.default_perspective_count,
            self.enforce_distinct_rir_regions,
            self.global_max_attempts,
            self.hash_secret
        )

        self.mpic_coordinator = MpicCoordinator(
            self.call_remote_perspective,
            self.mpic_coordinator_configuration
        )

    # This function is a "dumb" transport for serialized data to a remote perspective and a serialized response from the remote perspective.
    # MPIC Coordinator is tasked with ensuring the data from this function is sane. This function may raise an exception if something goes wrong.
    def call_remote_perspective(self, perspective: RemotePerspective, check_type: CheckType, check_request_serialized: str):
        # Uses dcv_arn_list, caa_arn_list
        client = boto3.client('lambda', perspective.code)
        function_name = self.arns_per_perspective_per_check_type[check_type][perspective.to_rir_code()]
        response = client.invoke(  # AWS Lambda-specific structure
                FunctionName=function_name,
                InvocationType='RequestResponse',
                Payload=check_request_serialized
            )
        response_payload = json.loads(response['Payload'].read().decode('utf-8'))
        return response_payload['body']

    def process_invocation(self, event):
        request_path = event['path']
        if request_path not in iter(RequestPath):
            return MpicCoordinator.build_400_response(MpicRequestValidationMessages.REQUEST_VALIDATION_FAILED.key,
                                                      [MpicRequestValidationMessages.UNSUPPORTED_REQUEST_PATH.key])

        return self.mpic_coordinator.coordinate_mpic(event['body'])


# Global instance for Lambda runtime
_handler = None


def get_handler() -> MpicCoordinatorLambdaHandler:
    """
    Singleton pattern to avoid recreating the handler on every Lambda invocation
    """
    global _handler
    if _handler is None:
        _handler = MpicCoordinatorLambdaHandler()
    return _handler


# noinspection PyUnusedLocal
# for now, we are not using context, but it is required by the lambda handler signature
def lambda_handler(event, context):  # AWS Lambda entry point
    return get_handler().process_invocation(event)

