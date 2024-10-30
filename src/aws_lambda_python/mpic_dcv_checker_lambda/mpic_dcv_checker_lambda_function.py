from aws_lambda_python.common_domain.remote_perspective import RemotePerspective
from aws_lambda_python.mpic_dcv_checker.mpic_dcv_checker import MpicDcvChecker
import os
import json


class MpicDcvCheckerLambdaHandler:
    def __init__(self):
        self.perspective = RemotePerspective.from_rir_code(os.environ['rir_region'] + "." + os.environ['AWS_REGION'])
        self.dcv_checker = MpicDcvChecker(self.perspective)

    def process_invocation(self, event):
        # Lambda seems to allow object transports. To make the code more generic for additional channels we only assume the transport is a string.
        # TODO reconsider this decision, potentially go back to passing an object to the caa_checker.check_caa method...
        return self.dcv_checker.check_dcv(json.dumps(event))


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
def lambda_handler(event, context):  # AWS Lambda entry point
    return get_handler().process_invocation(event)
