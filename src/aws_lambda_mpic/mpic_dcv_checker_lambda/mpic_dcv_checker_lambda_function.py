import asyncio

from aws_lambda_powertools.utilities.parser import event_parser

from open_mpic_core.common_domain.check_request import DcvCheckRequest
from open_mpic_core.mpic_dcv_checker.mpic_dcv_checker import MpicDcvChecker
import os


class MpicDcvCheckerLambdaHandler:
    def __init__(self):
        self.perspective_code = os.environ['AWS_REGION']
        self.dcv_checker = MpicDcvChecker(self.perspective_code)

    async def initialize(self):
        await self.dcv_checker.initialize()

    def process_invocation(self, dcv_request: DcvCheckRequest):
        try:
            event_loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running event loop, create a new one
            event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(event_loop)

        dcv_response = event_loop.run_until_complete(self.dcv_checker.check_dcv(dcv_request))
        status_code = 200
        if dcv_response.errors is not None and len(dcv_response.errors) > 0:
            if dcv_response.errors[0].error_type == '404':
                status_code = 404
            else:
                status_code = 500
        result = {
            'statusCode': status_code,
            'headers': {'Content-Type': 'application/json'},
            'body': dcv_response.model_dump_json()
        }
        return result


# Global instance for Lambda runtime
_handler = None


async def initialize_handler() -> MpicDcvCheckerLambdaHandler:
    handler = MpicDcvCheckerLambdaHandler()
    await handler.initialize()
    return handler


def get_handler() -> MpicDcvCheckerLambdaHandler:
    """
    Singleton pattern to avoid recreating the handler on every Lambda invocation
    """
    global _handler
    if _handler is None:
        try:
            event_loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running event loop, create a new one
            event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(event_loop)

        _handler = event_loop.run_until_complete(initialize_handler())
    return _handler


# noinspection PyUnusedLocal
# for now, we are not using context, but it is required by the lambda handler signature
@event_parser(model=DcvCheckRequest)
def lambda_handler(event: DcvCheckRequest, context):  # AWS Lambda entry point
    return get_handler().process_invocation(event)
