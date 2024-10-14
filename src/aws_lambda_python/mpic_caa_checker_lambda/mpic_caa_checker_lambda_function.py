from aws_lambda_python.mpic_caa_checker.mpic_caa_checker import MpicCaaChecker
caa_checker = MpicCaaChecker()


# noinspection PyUnusedLocal
def lambda_handler(event, context):
    return caa_checker.check_caa(event)
