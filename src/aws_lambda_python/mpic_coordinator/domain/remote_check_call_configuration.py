from aws_lambda_python.common_domain.check_request import BaseCheckRequest
from aws_lambda_python.common_domain.enum.check_type import CheckType
from aws_lambda_python.common_domain.remote_perspective import RemotePerspective


class RemoteCheckCallConfiguration:
    def __init__(self, check_type: CheckType, perspective: RemotePerspective, check_request: BaseCheckRequest):
        self.check_type = check_type
        self.perspective = perspective
        self.check_request = check_request
