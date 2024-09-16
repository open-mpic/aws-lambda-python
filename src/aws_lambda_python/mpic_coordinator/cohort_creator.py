from importlib import resources
from itertools import cycle, chain
import random
import yaml
from pydantic import TypeAdapter

from aws_lambda_python.mpic_coordinator.domain.remote_perspective import RemotePerspective


class CohortCreator:
    @staticmethod
    def build_randomly_shuffled_available_perspectives_per_rir(available_perspectives: list[str], random_seed: bytes) -> dict[str, list[RemotePerspective]]:
        # convert available_perspectives to a list of RemotePerspective objects
        remote_perspectives = []
        all_possible_perspectives_by_code = CohortCreator.load_aws_region_config()

        for perspective in available_perspectives:
            perspective_rir = perspective.split('.')[0]
            perspective_code = perspective.split('.')[1]

            if perspective_code not in all_possible_perspectives_by_code.keys():
                continue  # TODO throw an error? check this case in the validator?
            else:
                full_perspective = all_possible_perspectives_by_code[perspective_code]
                # TODO discuss: do we even need RIRs specified in the input? code should be unique enough
                remote_perspectives.append(full_perspective)

        random.seed(random_seed)
        random.shuffle(remote_perspectives)
        perspectives_per_rir = {}
        for perspective in remote_perspectives:
            if perspective.rir not in perspectives_per_rir:
                perspectives_per_rir[perspective.rir] = []
            perspectives_per_rir[perspective.rir].append(perspective)

        return perspectives_per_rir

    @staticmethod
    def load_aws_region_config():
        """
        Reads in the available AWS regions from a configuration yaml and returns them as a list.
        :return: list of available AWS regions
        """
        with resources.open_text('resources', 'aws_region_config.yaml') as file:
            aws_region_config_yaml = yaml.safe_load(file)
            aws_region_type_adapter = TypeAdapter(list[RemotePerspective])
            aws_regions_list = aws_region_type_adapter.validate_python(aws_region_config_yaml['aws_available_regions'])
            aws_regions_dict = {region.code: region for region in aws_regions_list}
            return aws_regions_dict

    @staticmethod
    def create_perspective_cohorts(perspectives_per_rir: dict, cohort_size: int):
        if cohort_size == 1:
            return [[region] for region in
                    chain.from_iterable(perspectives_per_rir.values())]  # TODO limit cohort number in this case?
        elif len(perspectives_per_rir.keys()) < 2:  # else if only one rir, can't meet requirements
            return []  # TODO throw an error? check this case in the validator?

        # the below is an upper bound for number of potential cohorts, assuming rir and distance rules can be met
        number_of_potential_cohorts = len(list(chain.from_iterable(perspectives_per_rir.values()))) // cohort_size
        new_cohorts, cohorts_with_two_rirs, full_cohorts = [], [], []
        for cohort_number in range(number_of_potential_cohorts):
            new_cohorts.append([])  # start with list of empty cohorts (list of lists)
        # get set of unique rirs from available_perspectives
        rirs_available = perspectives_per_rir.keys()
        # cycle through rirs in available_perspectives
        rirs_cycle = cycle(rirs_available)

        # first, try to fill up cohorts with 2 distinct rirs each
        cohort_index = 0
        for current_rir in rirs_available:
            while cohort_index < len(new_cohorts):
                cohort = new_cohorts[cohort_index]

                # if all out of perspectives for this rir, or already added this rir (looped back around)
                # then move on to the next rir
                if (len(perspectives_per_rir[current_rir]) == 0 or
                        current_rir in [perspective.rir for perspective in cohort]):
                    break  # break out of cohort loop to get next rir

                cohort.append(perspectives_per_rir[current_rir].pop(0))

                # if cohort has 2 rirs, move it to cohorts_with_two_rirs
                if len(cohort) == 2:
                    cohorts_with_two_rirs.append(new_cohorts.pop(cohort_index))
                else:
                    cohort_index += 1
                if cohort_index >= len(new_cohorts):
                    cohort_index = 0

        # iterate over new_cohorts and remove the ones left at this point (failed to distribute 2 rirs to them)
        for cohort in new_cohorts:
            for perspective in cohort:
                perspectives_per_rir[perspective.rir].append(perspective)
        new_cohorts.clear()

        # now we have a list of cohorts with 2 rirs; time to distribute the rest of the perspectives
        # try to fill up one cohort at a time (seems like simpler logic) than trying to fill all cohorts at once
        while len(cohorts_with_two_rirs) > 0:
            too_close_perspectives = []
            cohort = cohorts_with_two_rirs[0]  # get the (next) cohort
            # while the cohort isn't at its required size and there are still enough potential perspectives to add
            while len(cohort) < cohort_size and cohort_size - len(cohort) <= len(
                    list(chain.from_iterable(perspectives_per_rir.values()))):
                # get the next rir
                current_rir = next(rirs_cycle)

                # if we are all out of perspectives for this rir, move on to the next rir
                if len(perspectives_per_rir[current_rir]) == 0:
                    continue  # continue to next rir

                while len(perspectives_per_rir[current_rir]) > 0:
                    candidate_perspective = perspectives_per_rir[current_rir].pop(0)
                    if not any(candidate_perspective.is_perspective_too_close(perspective) for perspective in cohort):
                        cohort.append(candidate_perspective)
                        break
                    else:
                        too_close_perspectives.append(candidate_perspective)

            # if cohort is full, move it to full_cohorts
            if len(cohort) == cohort_size:
                full_cohorts.append(cohorts_with_two_rirs[0])
            else:  # otherwise, we ran out of perspectives to add to this cohort; it's a bad cohort so scrap it
                for perspective in cohort:
                    perspectives_per_rir[perspective.rir].append(perspective)
            del cohorts_with_two_rirs[0]
            # reset too_close_regions for next cohort
            for perspective in too_close_perspectives:
                perspectives_per_rir[perspective.rir].append(perspective)

        # now we have a list of full cohorts
        return full_cohorts
