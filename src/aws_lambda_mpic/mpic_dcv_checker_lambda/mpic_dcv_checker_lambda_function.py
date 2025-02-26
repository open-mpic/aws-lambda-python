import os
import asyncio

from aws_lambda_powertools.utilities.parser import event_parser

from open_mpic_core import DcvCheckRequest, MpicDcvChecker
from open_mpic_core import get_logger

logger = get_logger(__name__)


class MpicDcvCheckerLambdaHandler:
    def __init__(self):
        self.log_level = os.environ["log_level"] if "log_level" in os.environ else None
        self.http_client_timeout = (
            os.environ["dcv_http_client_timeout_seconds"] if "dcv_http_client_timeout_seconds" in os.environ else 30
        )

        self.logger = logger.getChild(self.__class__.__name__)
        if self.log_level:
            self.logger.setLevel(self.log_level)

        # don't reuse the http client, as lambda creates new event loops on each invocation
        self.dcv_checker = MpicDcvChecker(
            http_client_timeout=self.http_client_timeout, reuse_http_client=False, log_level=self.logger.level
        )

    def process_invocation(self, dcv_request: DcvCheckRequest):
        try:
            event_loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running event loop, create a new one
            event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(event_loop)

        self.logger.debug("(debug log) Processing DCV check request: %s", dcv_request)
        print("(print) Processing DCV check request: %s", dcv_request)

        dcv_response = event_loop.run_until_complete(self.dcv_checker.check_dcv(dcv_request))
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
        _handler = MpicDcvCheckerLambdaHandler()
    return _handler


# noinspection PyUnusedLocal
# for now, we are not using context, but it is required by the lambda handler signature
@event_parser(model=DcvCheckRequest)
def lambda_handler(event: DcvCheckRequest, context):  # AWS Lambda entry point
    return get_handler().process_invocation(event)
