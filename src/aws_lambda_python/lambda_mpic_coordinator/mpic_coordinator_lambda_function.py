import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__)))

# TODO consider tossing this into a layer
from mpic_coordinator import MpicCoordinator  # noqa: E402
coordinator = MpicCoordinator()


# noinspection PyUnusedLocal
# for now we are not using context, but it is required by the lambda handler signature
def lambda_handler(event, context):
    return coordinator.coordinate_mpic(event)
