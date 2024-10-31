from aws_lambda_powertools.utilities.parser import event_parser, envelopes
from pydantic import TypeAdapter
from open_mpic_core.common_domain.check_request import BaseCheckRequest
from open_mpic_core.common_domain.check_response import CheckResponse
from open_mpic_core.common_domain.validation_error import MpicValidationError
from open_mpic_core.mpic_coordinator.domain.mpic_request import MpicRequest
from open_mpic_core.mpic_coordinator.domain.mpic_request_validation_error import MpicRequestValidationError
from open_mpic_core.mpic_coordinator.mpic_coordinator import MpicCoordinator, MpicCoordinatorConfiguration
from open_mpic_core.common_domain.enum.check_type import CheckType
from open_mpic_core.common_domain.remote_perspective import RemotePerspective

import boto3
import os
import json


class MpicCoordinatorLambdaHandler:
    def __init__(self):
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

        # for correct deserialization of responses based on discriminator field (check type)
        self.mpic_request_adapter = TypeAdapter(MpicRequest)
        self.check_response_adapter = TypeAdapter(CheckResponse)

    # This function MUST validate its response and return a proper open_mpic_core object type.
    def call_remote_perspective(self, perspective: RemotePerspective, check_type: CheckType, check_request: BaseCheckRequest) -> CheckResponse:
        # Uses dcv_arn_list, caa_arn_list
        client = boto3.client('lambda', perspective.code)
        function_name = self.arns_per_perspective_per_check_type[check_type][perspective.to_rir_code()]
        response = client.invoke(  # AWS Lambda-specific structure
                FunctionName=function_name,
                InvocationType='RequestResponse',
                Payload=check_request.model_dump_json()  # AWS Lambda functions expect a JSON string for payload
            )
        response_payload = json.loads(response['Payload'].read().decode('utf-8'))
        return self.check_response_adapter.validate_json(response_payload['body'])

    def process_invocation(self, mpic_request: MpicRequest) -> dict:
        try:
            mpic_response = self.mpic_coordinator.coordinate_mpic(mpic_request)
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': mpic_response.model_dump_json()
            }
        except MpicRequestValidationError as e:  # TODO catch ALL exceptions here?
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': str(e)})
            }


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
@event_parser(model=MpicRequest, envelope=envelopes.ApiGatewayEnvelope)  # AWS Lambda Powertools decorator
def lambda_handler(event: MpicRequest, context):  # AWS Lambda entry point
    return get_handler().process_invocation(event)
