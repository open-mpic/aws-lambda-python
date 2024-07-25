import pytest
import os

import aws_lambda_python.lambda_controller.lambda_function as lambda_function


@pytest.fixture(scope="class")
def set_environment_variables():
    envvars = {
        "perspective_names": "rir1.region1a|rir1.region1b|rir2.region2a|rir2.region2b|rir3.region3a|rir3.region3b",
    }
    with pytest.MonkeyPatch.context() as class_scoped_monkeypatch:
        for k, v in envvars.items():
            class_scoped_monkeypatch.setenv(k, v)
        yield class_scoped_monkeypatch  # restore the environment afterward


class TestMpicOrchestrator:
    @pytest.mark.parametrize("requested_perspective_count, expected_unique_rirs", [(2, 2), (3, 3), (4, 3)])
    def test_random_select_perspectives_considering_rir_should_select_diverse_rirs_given_list_where_some_share_same_rir(
            self, set_environment_variables, requested_perspective_count, expected_unique_rirs):
        perspectives = os.getenv("perspective_names").split("|")  # same split logic as in actual calling code
        selected_perspectives = lambda_function.MpicOrchestrator.random_select_perspectives_considering_rir(perspectives, requested_perspective_count)
        assert len(set(map(lambda p: p.split('.')[0], selected_perspectives))) == expected_unique_rirs  # expect 3 unique rirs from setup data

    def test_random_select_perspectives_considering_rir_should_throw_error_given_requested_count_exceeds_total_perspectives(
            self, set_environment_variables):
        perspectives = os.getenv("perspective_names").split("|")
        with pytest.raises(ValueError):
            lambda_function.MpicOrchestrator.random_select_perspectives_considering_rir(perspectives, 10)  # expect error


if __name__ == '__main__':
    pytest.main()
