import pytest

from aws_lambda_python.mpic_coordinator.mpic_response_builder import MpicResponseBuilder


class TestMpicResponseBuilder:
    @pytest.mark.xfail  # FIXME: This test is expected to fail for now since nothing is implemented
    def test_build_response_should_return_response_with_given_status_code_and_body(self):
        MpicResponseBuilder.build_response(200, "test")
        assert False


if __name__ == '__main__':
    pytest.main()
