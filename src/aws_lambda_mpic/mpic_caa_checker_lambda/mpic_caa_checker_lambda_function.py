import os
import asyncio

from aws_lambda_powertools.utilities.parser import event_parser

from open_mpic_core import CaaCheckRequest
from open_mpic_core import MpicCaaChecker
from open_mpic_core import get_logger

logger = get_logger(__name__)


class MpicCaaCheckerLambdaHandler:
    def __init__(self):
        self.default_caa_domain_list = os.environ["default_caa_domains"].split("|")
        self.log_level = os.environ["log_level"] if "log_level" in os.environ else None

        self.logger = logger.getChild(self.__class__.__name__)
        if self.log_level:
            self.logger.setLevel(self.log_level)

        self.caa_checker = MpicCaaChecker(
            default_caa_domain_list=self.default_caa_domain_list, log_level=self.logger.level
        )

    def process_invocation(self, caa_request: CaaCheckRequest):
        caa_response = asyncio.get_event_loop().run_until_complete(self.caa_checker.check_caa(caa_request))
        result = {
            "statusCode": 200,  # note: must be snakeCase
            "headers": {"Content-Type": "application/json"},
            "body": caa_response.model_dump_json(),
        }
        return result


# Global instance for Lambda runtime
_handler = None


def get_handler() -> MpicCaaCheckerLambdaHandler:
    """
    Singleton pattern to avoid recreating the handler on every Lambda invocation
    """
    global _handler
    if _handler is None:
        event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(event_loop)
        _handler = MpicCaaCheckerLambdaHandler()
    return _handler


if os.environ.get("AWS_LAMBDA_FUNCTION_NAME") is not None:
    get_handler()


# noinspection PyUnusedLocal
# for now, we are not using context, but it is required by the lambda handler signature
@event_parser(model=CaaCheckRequest)
def lambda_handler(event: CaaCheckRequest, context):  # AWS Lambda entry point
    return get_handler().process_invocation(event)
