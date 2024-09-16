import hashlib
from importlib import resources
from itertools import chain, cycle
from pprint import pprint

import pytest
import yaml
from pydantic import TypeAdapter

from aws_lambda_python.mpic_coordinator.cohort_creator import CohortCreator
from aws_lambda_python.mpic_coordinator.domain.remote_perspective import RemotePerspective


# noinspection PyMethodMayBeStatic
class TestCohortCreator:
    @classmethod
    def setup_class(cls):
        cls.all_perspectives_per_rir = TestCohortCreator.set_up_perspectives_per_rir_dict_from_file()

    @pytest.mark.parametrize('named_perspectives', [
        (['arin.us-east-1', 'arin.us-west-1', 'arin.ca-west-1', 'ripe.eu-west-1', 'ripe.eu-central-1', 'apnic.ap-southeast-1',]),
    ])
    def build_randomly_shuffled_available_perspectives_per_rir__should_return_dict_of_remote_perspective_lists(self, named_perspectives):
        test_random_seed = hashlib.sha256('test1hash2seed3'.encode('ASCII')).digest()
        shuffled_perspectives_per_rir = CohortCreator.build_randomly_shuffled_available_perspectives_per_rir(
            named_perspectives, test_random_seed)
        # get all rirs from named perspectives
        all_rirs = set(map(lambda perspective: perspective.split('.')[0], named_perspectives))
        expected_perspectives_per_rir = {rir: [perspective for perspective in named_perspectives if perspective.startswith(rir)]
                                         for rir in all_rirs}
        assert len(shuffled_perspectives_per_rir.keys()) == len(all_rirs)
        for rir in shuffled_perspectives_per_rir.keys():
            assert len(shuffled_perspectives_per_rir[rir]) == len(expected_perspectives_per_rir[rir])

    def build_randomly_shuffled_available_perspectives_per_rir__should_shuffle_perspectives_the_same_given_the_same_random_seed(self):
        all_perspectives = list(chain.from_iterable(self.all_perspectives_per_rir.values()))
        all_perspectives_as_strings = list(map(lambda perspective: f"{perspective.rir}.{perspective.code}", all_perspectives))
        shuffled_perspectives_per_rir_1 = CohortCreator.build_randomly_shuffled_available_perspectives_per_rir(all_perspectives_as_strings, b'testSeedX')
        shuffled_perspectives_per_rir_2 = CohortCreator.build_randomly_shuffled_available_perspectives_per_rir(all_perspectives_as_strings, b'testSeedX')
        shuffled_perspectives_per_rir_3 = CohortCreator.build_randomly_shuffled_available_perspectives_per_rir(all_perspectives_as_strings, b'testSeedY')
        # expect 1 and 2 to be identically sorted, while 3 should be different
        assert all(shuffled_perspectives_per_rir_1[rir] == shuffled_perspectives_per_rir_2[rir] for rir in shuffled_perspectives_per_rir_1.keys())
        for rir in shuffled_perspectives_per_rir_1.keys():
            assert all(shuffled_perspectives_per_rir_1[rir][i] == shuffled_perspectives_per_rir_2[rir][i]
                       for i in range(len(shuffled_perspectives_per_rir_1[rir])))
        assert any(shuffled_perspectives_per_rir_1[rir] != shuffled_perspectives_per_rir_3[rir] for rir in shuffled_perspectives_per_rir_1.keys())

    def build_randomly_shuffled_available_perspectives_per_rir__should_return_empty_dict_given_empty_list_of_perspectives(self):
        shuffled_perspectives_per_rir = CohortCreator.build_randomly_shuffled_available_perspectives_per_rir([], b'testSeed')
        assert len(shuffled_perspectives_per_rir.keys()) == 0

    def build_randomly_shuffled_available_perspectives_per_rir__should_enrich_each_perspective_with_name_and_list_of_too_close_perspectives(self):
        named_perspectives = ['arin.us-east-1', 'arin.us-west-1', 'arin.ca-west-1', 'ripe.eu-west-1', 'ripe.eu-central-1', 'apnic.ap-southeast-1' ]
        shuffled_perspectives_per_rir = CohortCreator.build_randomly_shuffled_available_perspectives_per_rir(named_perspectives, b'testSeed')
        shuffled_perspectives_flattened = list(chain.from_iterable(shuffled_perspectives_per_rir.values()))
        assert all(perspective.name is not None for perspective in shuffled_perspectives_flattened)
        assert any(len(perspective.too_close_codes) > 0 for perspective in shuffled_perspectives_flattened)

    def load_aws_region_config__should_return_dict_of_aws_regions_with_proximity_info_by_region_code(self):
        loaded_aws_regions = CohortCreator.load_aws_region_config()
        all_perspectives = list(chain.from_iterable(self.all_perspectives_per_rir.values()))
        assert len(loaded_aws_regions.keys()) == len(all_perspectives)
        # for example, us-east-1 is too close to us-east-2
        assert 'us-east-2' in loaded_aws_regions['us-east-1'].too_close_codes
        assert 'us-east-1' in loaded_aws_regions['us-east-2'].too_close_codes

    # @pytest.mark.skip('This test is not yet implemented')
    @pytest.mark.parametrize('perspectives_per_rir, any_perspectives_too_close, cohort_size', [
        # perspectives_per_rir expects: (total_perspectives, total_rirs, max_per_rir, too_close_flag)
        ((3, 2, 2, False), False, 1),  # expect 3 cohorts of 1
        ((3, 2, 2, False), False, 2),  # expect 1 cohort of 2
        ((6, 3, 2, False), False, 2),  # expect 3 cohorts of 2
        ((6, 3, 2, True), True, 2),  # expect 3 cohorts of 2
        ((10, 2, 5, False), False, 5),  # expect 2 cohorts of 5
        ((10, 2, 5, True), True, 5),  # expect 1 cohort of 5
        ((10, 2, 5, True), True, 4),  # expect 2 cohorts of 4
        ((18, 5, 8, True), True, 6),  # expect 3 cohorts of 6
        ((18, 5, 8, False), False, 6),  # expect 3 cohorts of 6
        ((18, 3, 6, True), True, 6),  # expect 3 cohorts of 6
        ((18, 5, 7, True), True, 15),  # expect 1 cohort of 15
    ], indirect=['perspectives_per_rir'])
    def create_perspective_cohorts__should_return_set_of_cohorts_with_requested_size(self, perspectives_per_rir,
                                                                                     any_perspectives_too_close,
                                                                                     cohort_size):
        total_perspectives = len(list(chain.from_iterable(perspectives_per_rir.values())))
        print(f"\ntotal perspectives: {total_perspectives}")
        print(f"total rirs: {len(perspectives_per_rir.keys())}")
        print(f"any perspectives too close: {any_perspectives_too_close}")
        pprint(perspectives_per_rir)
        cohorts = CohortCreator.create_perspective_cohorts(perspectives_per_rir, cohort_size)
        print(f"total cohorts created: {len(cohorts)}")
        pprint(cohorts)
        assert len(cohorts) > 0
        if not any_perspectives_too_close:  # if no perspectives were too close, should have max possible cohorts
            assert len(cohorts) == total_perspectives // cohort_size
        for cohort in cohorts:
            assert len(cohort) == cohort_size
            # assert that no two perspectives in the cohort are too close to each other
            for i in range(len(cohort)):
                for j in range(i + 1, len(cohort)):
                    assert not cohort[i].is_perspective_too_close(cohort[j])
            # assert that all cohorts have at least 2 RIRs (unless desired cohort size is 1)
            if cohort_size > 1:
                assert len(set(map(lambda perspective: perspective.rir, cohort))) >= 2

    @pytest.mark.parametrize('perspectives_per_rir, any_perspectives_too_close, cohort_size', [
        # perspectives_per_rir expects: (total_perspectives, total_rirs, max_per_rir, too_close_flag)
        ((3, 1, 3, False), False, 3),  # expect 0 cohorts due to too few rirs
        ((3, 2, 2, True), True, 3),  # expect 0 cohorts due to too close perspectives
        ((18, 5, 8, True), True, 18),  # expect 0 cohorts due to too close perspectives
    ], indirect=['perspectives_per_rir'])
    def create_perspective_cohorts__should_return_0_cohorts_given_no_cohort_would_meet_requirements(self, perspectives_per_rir,
                                                                                                    any_perspectives_too_close,
                                                                                                    cohort_size):
        print(f"\ntotal perspectives: {len(list(chain.from_iterable(perspectives_per_rir.values())))}")
        print(f"total rirs: {len(perspectives_per_rir.keys())}")
        print(f"any perspectives too close: {any_perspectives_too_close}")
        pprint(perspectives_per_rir)
        cohorts = CohortCreator.create_perspective_cohorts(perspectives_per_rir, cohort_size)
        assert len(cohorts) == 0

    def create_perspective_cohorts__should_handle_uneven_numbers_of_perspectives_per_rir(self):
        # 9 total perspectives, but can only make 2 cohorts of 3 perspectives each due to rir constraints
        perspectives_per_rir = {'apnic': self.all_perspectives_per_rir['apnic'][:7],  # 7 perspectives from apnic
                                'ripe': self.all_perspectives_per_rir['ripe'][:1],  # 1 from ripe
                                'arin': self.all_perspectives_per_rir['arin'][:1]}  # 1 from arin
        cohorts = CohortCreator.create_perspective_cohorts(perspectives_per_rir, 3)
        assert len(cohorts) == 2

    @pytest.fixture
    def perspectives_per_rir(self, request):
        total_perspectives = request.param[0]
        total_rirs = request.param[1]
        max_per_rir = request.param[2]
        too_close_flag = request.param[3]
        return self.create_perspectives_per_rir_given_requirements(total_perspectives, total_rirs, max_per_rir,
                                                                   too_close_flag)

    def create_perspectives_per_rir_given_requirements(self, total_perspectives, total_rirs, max_per_rir,
                                                       too_close_flag):
        assert total_perspectives <= total_rirs * max_per_rir
        # get set (unique) of all rirs found in all_available_perspectives, each of which has a rir attribute
        perspectives_per_rir = dict[str, list[RemotePerspective]]()
        total_perspectives_added = 0
        # set ordered_rirs to be a list of rirs ordered in descending order based on number of perspectives for each rir in all_perspectives_per_rir
        all_rirs = list(self.all_perspectives_per_rir.keys())
        all_rirs.sort(key=lambda rir: len(self.all_perspectives_per_rir[rir]), reverse=True)
        while len(all_rirs) > total_rirs:
            all_rirs.pop()
        # in case total_perspectives is too high for the number actually available in the rirs left
        max_available_perspectives = sum(len(self.all_perspectives_per_rir[rir]) for rir in all_rirs)

        rirs_cycle = cycle(all_rirs)
        while total_perspectives_added < total_perspectives and total_perspectives_added < max_available_perspectives:
            current_rir = next(rirs_cycle)
            all_perspectives_for_rir: list[RemotePerspective] = list(self.all_perspectives_per_rir[current_rir])
            if current_rir not in perspectives_per_rir.keys():
                perspectives_per_rir[current_rir] = []
            while (len(perspectives_per_rir[current_rir]) < max_per_rir
                   and len(all_perspectives_for_rir) > 0
                   and total_perspectives_added < total_perspectives):
                if too_close_flag and len(perspectives_per_rir[current_rir]) == 0:
                    # find two perspectives in all_perspectives_for_rir that are too close to each other
                    first_too_close_index = 0
                    first_too_close_perspective = None
                    second_too_close_index = 0
                    for i in range(len(all_perspectives_for_rir)):
                        if len(all_perspectives_for_rir[i].too_close_codes) > 0:
                            first_too_close_index = i
                            first_too_close_perspective = all_perspectives_for_rir[i]
                            break
                    for j in range(first_too_close_index + 1, len(all_perspectives_for_rir)):
                        if first_too_close_perspective.is_perspective_too_close(all_perspectives_for_rir[j]):
                            second_too_close_index = j
                            break
                    if second_too_close_index > 0:  # found two too close perspectives
                        # pop the later one first so that the earlier one is not affected by the index change
                        perspectives_per_rir[current_rir].append(all_perspectives_for_rir.pop(second_too_close_index))
                        perspectives_per_rir[current_rir].append(all_perspectives_for_rir.pop(first_too_close_index))
                        total_perspectives_added += 2
                        continue

                perspective_to_add = all_perspectives_for_rir.pop(0)
                if not any(perspective_to_add.is_perspective_too_close(perspective) for perspective in
                           perspectives_per_rir[current_rir]):
                    perspectives_per_rir[current_rir].append(perspective_to_add)
                    total_perspectives_added += 1
                else:
                    continue

        return perspectives_per_rir

    @staticmethod
    def set_up_perspectives_per_rir_dict_from_file():
        perspectives_yaml = yaml.safe_load(resources.open_text('resources', 'aws_region_config.yaml'))
        perspective_type_adapter = TypeAdapter(list[RemotePerspective])
        perspectives = perspective_type_adapter.validate_python(perspectives_yaml['aws_available_regions'])
        # get set of unique rirs from perspectives, each of which has a rir attribute
        all_rirs = set(map(lambda perspective: perspective.rir, perspectives))
        return {rir: [perspective for perspective in perspectives if perspective.rir == rir] for rir in all_rirs}
