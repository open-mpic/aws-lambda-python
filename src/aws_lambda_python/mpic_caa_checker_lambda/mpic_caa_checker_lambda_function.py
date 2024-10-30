from aws_lambda_python.common_domain.remote_perspective import RemotePerspective
from aws_lambda_python.mpic_caa_checker.mpic_caa_checker import MpicCaaChecker
import os
import json


class MpicCaaCheckerLambdaHandler:
    def __init__(self):
        self.perspective = RemotePerspective.from_rir_code(os.environ['rir_region'] + "." + os.environ['AWS_REGION'])
        self.default_caa_domain_list = os.environ['default_caa_domains'].split("|")
        self.caa_checker = MpicCaaChecker(self.default_caa_domain_list, self.perspective)

    def process_invocation(self, event):
        # Lambda seems to allow object transports. To make the code more generic for additional channels we only assume the transport is a string.
        # TODO reconsider this decision, potentially go back to passing an object to the caa_checker.check_caa method...
        return self.caa_checker.check_caa(json.dumps(event))


# Global instance for Lambda runtime
_handler = None


def get_handler() -> MpicCaaCheckerLambdaHandler:
    """
    Singleton pattern to avoid recreating the handler on every Lambda invocation
    """
    global _handler
    if _handler is None:
        _handler = MpicCaaCheckerLambdaHandler()
    return _handler


# noinspection PyUnusedLocal
# for now, we are not using context, but it is required by the lambda handler signature
def lambda_handler(event, context):  # AWS Lambda entry point
    return get_handler().process_invocation(event)
