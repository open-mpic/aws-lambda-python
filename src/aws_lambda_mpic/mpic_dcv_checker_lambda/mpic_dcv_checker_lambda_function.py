import os
import asyncio

from aws_lambda_powertools.utilities.parser import event_parser

from open_mpic_core import DcvCheckRequest, MpicDcvChecker
from open_mpic_core import get_logger

logger = get_logger(__name__)


class MpicDcvCheckerLambdaHandler:
    def __init__(self):
        self.log_level = os.environ["log_level"] if "log_level" in os.environ else None

        self.logger = logger.getChild(self.__class__.__name__)
        if self.log_level:
            self.logger.setLevel(self.log_level)

        self.dcv_checker = MpicDcvChecker(reuse_http_client=False, log_level=self.logger.level)

    def process_invocation(self, dcv_request: DcvCheckRequest):
        self.logger.debug("(debug log) Processing DCV check request: %s", dcv_request)
        print("(print) Processing DCV check request: %s", dcv_request)

        dcv_response = asyncio.get_event_loop().run_until_complete(self.dcv_checker.check_dcv(dcv_request))
        status_code = 200
        if dcv_response.errors is not None and len(dcv_response.errors) > 0:
            if dcv_response.errors[0].error_type == "404":
                status_code = 404
            else:
                status_code = 500
        result = {
            "statusCode": status_code,
            "headers": {"Content-Type": "application/json"},
            "body": dcv_response.model_dump_json(),
        }
        return result


# Global instance for Lambda runtime
_handler = None


def get_handler() -> MpicDcvCheckerLambdaHandler:
    """
    Singleton pattern to avoid recreating the handler on every Lambda invocation
    """
    global _handler
    if _handler is None:
        event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(event_loop)
        _handler = MpicDcvCheckerLambdaHandler()
    return _handler


if os.environ.get("AWS_LAMBDA_FUNCTION_NAME") is not None:
    get_handler()


# noinspection PyUnusedLocal
# for now, we are not using context, but it is required by the lambda handler signature
@event_parser(model=DcvCheckRequest)
def lambda_handler(event: DcvCheckRequest, context):  # AWS Lambda entry point
    return get_handler().process_invocation(event)
