# from aws_lambda_python.lambda_controller.mpic_orchestrator import MpicOrchestrator
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__)))


# noinspection PyUnusedLocal
# for now we are not using context, but it is required by the lambda handler signature
def lambda_handler(event, context):
    from mpic_orchestrator import MpicOrchestrator
    orchestrator = MpicOrchestrator()
    return orchestrator.orchestrate_mpic(event)
