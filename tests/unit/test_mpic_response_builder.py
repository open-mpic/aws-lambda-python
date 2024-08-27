import json
import pytest
from aws_lambda_python.common_domain.check_response import CaaCheckResponse, DcvCheckResponse, CaaCheckResponseDetails, DcvCheckResponseDetails
from aws_lambda_python.common_domain.enum.check_type import CheckType
from aws_lambda_python.mpic_coordinator.domain.mpic_response import BaseMpicResponse, AnnotatedMpicResponse, \
    MpicDcvResponse
from aws_lambda_python.mpic_coordinator.mpic_response_builder import MpicResponseBuilder
from pydantic import TypeAdapter

from valid_request_creator import ValidRequestCreator


class TestMpicResponseBuilder:
    @staticmethod
    def create_perspective_responses_per_check_type(check_type=CheckType.DCV_WITH_CAA):
        responses = {}
        caa_responses = [  # 1 false
            CaaCheckResponse(perspective='p1', check_passed=True, details=CaaCheckResponseDetails(caa_record_present=False)),
            CaaCheckResponse(perspective='p2', check_passed=False, details=CaaCheckResponseDetails(caa_record_present=False)),
            CaaCheckResponse(perspective='p3', check_passed=True, details=CaaCheckResponseDetails(caa_record_present=False)),
            CaaCheckResponse(perspective='p4', check_passed=True, details=CaaCheckResponseDetails(caa_record_present=False)),
            CaaCheckResponse(perspective='p5', check_passed=True, details=CaaCheckResponseDetails(caa_record_present=False)),
            CaaCheckResponse(perspective='p6', check_passed=True, details=CaaCheckResponseDetails(caa_record_present=False))
        ]
        dcv_responses = [  # 2 false
            DcvCheckResponse(perspective='p1', check_passed=True, details=DcvCheckResponseDetails()),
            DcvCheckResponse(perspective='p2', check_passed=True, details=DcvCheckResponseDetails()),
            DcvCheckResponse(perspective='p3', check_passed=True, details=DcvCheckResponseDetails()),
            DcvCheckResponse(perspective='p4', check_passed=True, details=DcvCheckResponseDetails()),
            DcvCheckResponse(perspective='p5', check_passed=False, details=DcvCheckResponseDetails()),
            DcvCheckResponse(perspective='p6', check_passed=False, details=DcvCheckResponseDetails())
        ]

        match check_type:
            case CheckType.CAA:
                responses[CheckType.CAA] = caa_responses
            case CheckType.DCV:
                responses[CheckType.DCV] = dcv_responses
            case CheckType.DCV_WITH_CAA:
                responses[CheckType.CAA] = caa_responses
                responses[CheckType.DCV] = dcv_responses

        return responses

    @staticmethod
    def create_validity_by_check_type(request_path=CheckType.DCV_WITH_CAA):
        validity_by_check_type = {}
        match request_path:
            case CheckType.CAA:
                validity_by_check_type[CheckType.CAA] = True
            case CheckType.DCV:
                validity_by_check_type[CheckType.DCV] = False
            case CheckType.DCV_WITH_CAA:
                validity_by_check_type[CheckType.CAA] = True
                validity_by_check_type[CheckType.DCV] = True
        return validity_by_check_type

    @pytest.mark.parametrize('check_type, perspective_count, quorum_count', [
        (CheckType.CAA, 6, 4),
        (CheckType.DCV, 6, 5),  # higher quorum count
        (CheckType.DCV_WITH_CAA, 6, 4)
    ])
    def build_response__should_return_response_given_mpic_request_configuration_and_results(self, check_type, perspective_count, quorum_count):
        persp_responses_per_check_type = self.create_perspective_responses_per_check_type(check_type)
        valid_by_check_type = self.create_validity_by_check_type(check_type)
        request = ValidRequestCreator.create_valid_request(check_type)
        response = MpicResponseBuilder.build_response(request, perspective_count, quorum_count,
                                                      persp_responses_per_check_type, valid_by_check_type)
        assert response['statusCode'] == 200

        mpic_response_adapter = TypeAdapter(AnnotatedMpicResponse)
        response_body = mpic_response_adapter.validate_python(json.loads(response['body']))

        assert (response_body.request_orchestration_parameters.perspective_count ==
                request.orchestration_parameters.perspective_count)
        assert response_body.actual_orchestration_parameters.perspective_count == perspective_count
        assert response_body.actual_orchestration_parameters.quorum_count == quorum_count

        match check_type:
            case CheckType.CAA:
                # response_body = MpicCaaResponse.model_validate(json.loads(response['body']))
                assert response_body.perspectives == persp_responses_per_check_type[CheckType.CAA]
                assert response_body.is_valid == valid_by_check_type[CheckType.CAA]
            case CheckType.DCV:
                assert response_body.perspectives == persp_responses_per_check_type[CheckType.DCV]
                assert response_body.is_valid == valid_by_check_type[CheckType.DCV]
            case CheckType.DCV_WITH_CAA:
                assert response_body.perspectives_dcv == persp_responses_per_check_type[CheckType.DCV]
                assert response_body.perspectives_caa == persp_responses_per_check_type[CheckType.CAA]
                assert response_body.is_valid_dcv == valid_by_check_type[CheckType.DCV]
                assert response_body.is_valid_caa == valid_by_check_type[CheckType.CAA]
                assert response_body.is_valid == response_body.is_valid_dcv and response_body.is_valid_caa

    def build_response__should_include_validation_details_and_method_when_present_in_request_body(self):
        request = ValidRequestCreator.create_valid_dcv_check_request()
        persp_responses_per_check_type = self.create_perspective_responses_per_check_type(CheckType.DCV)
        valid_by_check_type = self.create_validity_by_check_type(CheckType.DCV)
        response = MpicResponseBuilder.build_response(request, 6, 5, persp_responses_per_check_type,
                                                      valid_by_check_type)
        response_body = MpicDcvResponse.model_validate(json.loads(response['body']))
        assert response_body.dcv_parameters.validation_details.expected_challenge == request.dcv_check_parameters.validation_details.expected_challenge
        assert response_body.dcv_parameters.validation_method == request.dcv_check_parameters.validation_method

    def build_response__should_set_is_valid_to_false_when_either_check_type_is_invalid(self):
        request = ValidRequestCreator.create_valid_dcv_with_caa_check_request()
        persp_responses_per_check_type = self.create_perspective_responses_per_check_type(CheckType.DCV_WITH_CAA)
        valid_by_check_type = self.create_validity_by_check_type(CheckType.DCV_WITH_CAA)
        valid_by_check_type[CheckType.DCV] = False
        response = MpicResponseBuilder.build_response(request, 6, 4, persp_responses_per_check_type, valid_by_check_type)
        response_body = BaseMpicResponse.model_validate(json.loads(response['body']))
        assert response_body.is_valid is False


if __name__ == '__main__':
    pytest.main()
