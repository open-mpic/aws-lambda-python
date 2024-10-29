import pytest

from aws_lambda_python.mpic_coordinator.domain.remote_check_call_configuration import RemoteCheckCallConfiguration


class TestMpicCoordinatorLambda:
    @pytest.mark.skip(reason='not yet implemented')
    def thread_call__should_call_lambda_function_with_correct_parameters(self, set_env_variables, mocker):
        mocker.patch('botocore.client.BaseClient._make_api_call',
                     side_effect=self.create_successful_boto3_api_call_response)
        mpic_coordinator_configuration = self.create_mpic_coordinator_configuration()
        mpic_coordinator = MpicCoordinator(self.create_successful_remote_caa_check_response, mpic_coordinator_configuration)
        mpic_coordinator = MpicCoordinator()
        mpic_request = ValidRequestCreator.create_valid_dcv_mpic_request()
        check_request = DcvCheckRequest(domain_or_ip_target='using.for.test',
                                        dcv_check_parameters=mpic_request.dcv_check_parameters)
        call_config = RemoteCheckCallConfiguration(CheckType.DCV, RemotePerspective(code='us-east-2', rir='arin'),
                                                   lambda_arn='test_arn', check_request=check_request)
        response = mpic_coordinator.thread_call(call_config)
        perspective_response = json.loads(response['Payload'].read().decode('utf-8'))
        perspective_response_body = json.loads(perspective_response['body'])
        check_response = DcvCheckResponse.model_validate(perspective_response_body)
        assert check_response.check_passed is True
        # hijacking the value of 'perspective' to verify that the right arguments got passed to the call
        assert check_response.perspective == check_request.domain_or_ip_target
