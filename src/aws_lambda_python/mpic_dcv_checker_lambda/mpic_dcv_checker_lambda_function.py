from aws_lambda_python.common_domain.remote_perspective import RemotePerspective
from aws_lambda_python.mpic_dcv_checker.mpic_dcv_checker import MpicDcvChecker, MpicDcvCheckerConfiguration
import os
import json

# FIXME extract into a class for testing
dcv_checker_configuration = MpicDcvCheckerConfiguration(RemotePerspective.from_rir_code(os.environ['rir_region'] + "." + os.environ['AWS_REGION']))
dcv_checker = MpicDcvChecker()


# noinspection PyUnusedLocal
def lambda_handler(event, context):
    return dcv_checker.check_dcv(json.dumps(event))
