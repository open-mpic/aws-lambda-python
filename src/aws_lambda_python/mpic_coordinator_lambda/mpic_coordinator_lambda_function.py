from aws_lambda_python.mpic_coordinator.mpic_coordinator import MpicCoordinator
coordinator = MpicCoordinator()


# noinspection PyUnusedLocal
# for now we are not using context, but it is required by the lambda handler signature
def lambda_handler(event, context):
    return coordinator.coordinate_mpic(event)
