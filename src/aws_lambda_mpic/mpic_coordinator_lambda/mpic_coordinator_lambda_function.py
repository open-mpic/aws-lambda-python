import os
import json
import traceback

import yaml
import asyncio
import aioboto3

from asyncio import Queue
from collections import defaultdict
from importlib import resources
from pydantic import TypeAdapter, ValidationError, BaseModel
from aws_lambda_powertools.utilities.parser import event_parser, envelopes

from open_mpic_core import MpicRequest, CheckRequest, CheckResponse
from open_mpic_core import MpicRequestValidationException, MpicRequestValidationMessages
from open_mpic_core import MpicCoordinator, MpicCoordinatorConfiguration
from open_mpic_core import CheckType
from open_mpic_core import RemotePerspective
from open_mpic_core import get_logger

logger = get_logger(__name__)


class PerspectiveEndpointInfo(BaseModel):
    arn: str


class PerspectiveEndpoints(BaseModel):
    dcv_endpoint_info: PerspectiveEndpointInfo
    caa_endpoint_info: PerspectiveEndpointInfo


class LambdaExecutionException(Exception):
    pass


class MpicCoordinatorLambdaHandler:
    def __init__(self):
        perspectives_json = os.environ["perspectives"]
        perspectives = {
            code: PerspectiveEndpoints.model_validate(endpoints)
            for code, endpoints in json.loads(perspectives_json).items()
        }
        self._all_target_perspective_codes = list(perspectives.keys())
        self.default_perspective_count = int(os.environ["default_perspective_count"])
        self.global_max_attempts = (
            int(os.environ["absolute_max_attempts"]) if "absolute_max_attempts" in os.environ else None
        )
        self.hash_secret = os.environ["hash_secret"]
        self.log_level = os.getenv("log_level", None)

        self.logger = logger.getChild(self.__class__.__name__)
        if self.log_level:
            self.logger.setLevel(self.log_level)

        self.remotes_per_perspective_per_check_type = {
            CheckType.DCV: {
                perspective_code: perspective_config.dcv_endpoint_info
                for perspective_code, perspective_config in perspectives.items()
            },
            CheckType.CAA: {
                perspective_code: perspective_config.caa_endpoint_info
                for perspective_code, perspective_config in perspectives.items()
            },
        }

        all_possible_perspectives_by_code = MpicCoordinatorLambdaHandler.load_aws_region_config()
        self.target_perspectives = MpicCoordinatorLambdaHandler.convert_codes_to_remote_perspectives(
            self._all_target_perspective_codes, all_possible_perspectives_by_code
        )

        self.mpic_coordinator_configuration = MpicCoordinatorConfiguration(
            self.target_perspectives, self.default_perspective_count, self.global_max_attempts, self.hash_secret
        )

        self.mpic_coordinator = MpicCoordinator(
            self.call_remote_perspective, self.mpic_coordinator_configuration, self.logger.level
        )

        # for correct deserialization of responses based on discriminator field (check type)
        self.mpic_request_adapter = TypeAdapter(MpicRequest)
        self.check_response_adapter = TypeAdapter(CheckResponse)

        self._clients = {}
        asyncio.get_event_loop().run_until_complete(self.initialize_clients())

    async def initialize_clients(self):
        session = aioboto3.Session()
        for perspective_code in self._all_target_perspective_codes:
            self._clients[perspective_code] = await session.client("lambda", perspective_code).__aenter__()

    @staticmethod
    def load_aws_region_config() -> dict[str, RemotePerspective]:
        """
        Reads in the available perspectives from a configuration yaml and returns them as a dict (map).
        :return: dict of available perspectives with region code as key
        """
        with resources.files("resources").joinpath("aws_region_config.yaml").open("r") as file:
            aws_region_config_yaml = yaml.safe_load(file)
            aws_region_type_adapter = TypeAdapter(list[RemotePerspective])
            aws_regions_list = aws_region_type_adapter.validate_python(aws_region_config_yaml["aws_available_regions"])
            aws_regions_dict = {region.code: region for region in aws_regions_list}
            return aws_regions_dict

    @staticmethod
    def convert_codes_to_remote_perspectives(
        perspective_codes: list[str], all_possible_perspectives_by_code: dict[str, RemotePerspective]
    ) -> list[RemotePerspective]:
        remote_perspectives = []

        for perspective_code in perspective_codes:
            if perspective_code not in all_possible_perspectives_by_code.keys():
                continue  # TODO throw an error? check this case in the validator?
            else:
                fully_defined_perspective = all_possible_perspectives_by_code[perspective_code]
                remote_perspectives.append(fully_defined_perspective)

        return remote_perspectives

    # This function MUST validate its response and return a proper open_mpic_core object type.
    async def call_remote_perspective(
        self, perspective: RemotePerspective, check_type: CheckType, check_request: CheckRequest
    ) -> CheckResponse:
        client = self._clients[perspective.code]
        function_endpoint_info = self.remotes_per_perspective_per_check_type[check_type][perspective.code]
        response = await client.invoke(  # AWS Lambda-specific structure
            FunctionName=function_endpoint_info.arn,
            InvocationType="RequestResponse",
            Payload=check_request.model_dump_json(),  # AWS Lambda functions expect a JSON string for payload
        )
        response_payload = await response["Payload"].read()
        if 'FunctionError' in response:
            raise LambdaExecutionException(f"Lambda execution error: {response_payload.decode('utf-8')}")
        response_payload = json.loads(response_payload)
        return self.check_response_adapter.validate_json(response_payload["body"])

    def process_invocation(self, mpic_request: MpicRequest) -> dict:
        mpic_response = asyncio.get_event_loop().run_until_complete(self.mpic_coordinator.coordinate_mpic(mpic_request))
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": mpic_response.model_dump_json(),
        }


# Global instance for Lambda runtime
_handler = None

def get_handler() -> MpicCoordinatorLambdaHandler:
    """
    Singleton pattern to avoid recreating the handler on every Lambda invocation.
    Performs lazy initialization using event loop.
    """
    global _handler
    if _handler is None:
        event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(event_loop)
        _handler = MpicCoordinatorLambdaHandler()
    return _handler

# Eagerly initialize the handler if not running in a test environment.
if os.environ.get("PYTEST_VERSION") is None:
    get_handler()

def handle_lambda_exceptions(func):
    def build_400_response(error_name, issues_list):
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": error_name, "validation_issues": issues_list}),
        }

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except MpicRequestValidationException as e:
            validation_issues = json.loads(e.__notes__[0])
            return build_400_response(MpicRequestValidationMessages.REQUEST_VALIDATION_FAILED.key, validation_issues)
        except ValidationError as validation_error:
            return build_400_response(
                MpicRequestValidationMessages.REQUEST_VALIDATION_FAILED.key, validation_error.errors()
            )
        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
            print(traceback.format_exc())
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": str(e)}),
            }

    return wrapper


# noinspection PyUnusedLocal
# for now, we are not using context, but it is required by the lambda handler signature
@handle_lambda_exceptions
@event_parser(model=MpicRequest, envelope=envelopes.ApiGatewayEnvelope)  # AWS Lambda Powertools decorator
def lambda_handler(event: MpicRequest, context):  # AWS Lambda entry point
    return get_handler().process_invocation(event)
