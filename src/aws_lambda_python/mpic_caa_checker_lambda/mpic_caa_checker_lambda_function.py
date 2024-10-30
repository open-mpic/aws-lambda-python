from aws_lambda_python.common_domain.remote_perspective import RemotePerspective
from aws_lambda_python.mpic_caa_checker.mpic_caa_checker import MpicCaaChecker, MpicCaaCheckerConfiguration
import os
import json

# FIXME extract into a class for testing
perspective_identity = RemotePerspective.from_rir_code(os.environ['rir_region'] + "." + os.environ['AWS_REGION'])
default_caa_domain_list = os.environ['default_caa_domains'].split("|")

caa_checker_configuration = MpicCaaCheckerConfiguration(default_caa_domain_list, perspective_identity)
caa_checker = MpicCaaChecker(caa_checker_configuration)

class MpicCaaCheckerLambdaHandler:
    def __init__(self):
        self._initialize_config()

    def _initialize_config(self):
        self.perspective_identity = RemotePerspective.from_rir_code(os.environ['rir_region'] + "." + os.environ['AWS_REGION'])
        self.default_caa_domain_list = os.environ['default_caa_domains'].split("|")
        self.caa_checker_configuration = MpicCaaCheckerConfiguration(self.default_caa_domain_list, self.perspective_identity)
        self.caa_checker = MpicCaaChecker(self.caa_checker_configuration)


# noinspection PyUnusedLocal
def lambda_handler(event, context):
    # Lambda seems to allow object transports. To make the code more generic for additional channels we only assume the transport is a string.
    return caa_checker.check_caa(json.dumps(event))
