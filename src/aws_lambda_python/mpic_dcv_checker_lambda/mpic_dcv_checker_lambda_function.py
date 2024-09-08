from aws_lambda_python.mpic_dcv_checker.mpic_dcv_checker import MpicDcvChecker
dcv_checker = MpicDcvChecker()


# noinspection PyUnusedLocal
def lambda_handler(event, context):
    return dcv_checker.check_dcv(event)