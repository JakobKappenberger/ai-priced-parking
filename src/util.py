# from environment import CustomEnvironment
import re
from glob import glob
from pathlib import Path
from typing import List, Dict

import numpy as np


def occupancy_reward_function(colours: List[str], current_state: Dict[str, float], global_mode=False):
    """
    Rewards occupancy rates between 75% and 90%. Punishes deviations as the squared deviation from the target range.
    :param current_state:
    :param colours:
    :param global_mode:
    :return:
    """
    reward = 0
    if global_mode:
        cpz_occupancies = [current_state['overall_occupancy']]
    else:
        cpz_occupancies = [current_state[f'{c}-lot occupancy'] for c in colours]

    for val in cpz_occupancies:
        if val <= 0.825:
            reward += 1 - (abs(val - 0.825) / 0.825) ** 0.4
        else:
            value = 1 - (abs(val - 0.825) / 0.825) ** 0.4
            min_value = 1 - (abs(1 - 0.825) / 0.825) ** 0.4
            max_value = 1 - (abs(0.825 - 0.825) / 0.825) ** 0.4
            max_distance = max_value - min_value
            actual_distance = value - min_value
            reward += actual_distance / max_distance

    return reward / len(cpz_occupancies)


def n_cars_reward_function(colours: List[str], current_state: Dict[str, float]):
    """

    :param colours:
    :param current_state:
    :return:
    """
    return optimize_attr(current_state, "n_cars", mode="min")


def social_reward_function(colours: List[str], current_state: Dict[str, float]):
    """

    :param colours:
    :param current_state:
    :return:
    """
    return optimize_attr(current_state, "income_entropy")


def speed_reward_function(colours: List[str], current_state: Dict[str, float]):
    """

    :param colours:
    :param current_state:
    :return:
    """
    return optimize_attr(current_state, "mean_speed")


def composite_reward_function(colours: List[str], current_state: Dict[str, float]):
    """

    :param colours:
    :param current_state:
    :return:
    """
    return 0.5 * occupancy_reward_function(colours, current_state, global_mode=True) + 0.25 * n_cars_reward_function(
        colours, current_state) + 0.25 * social_reward_function(colours, current_state)


def optimize_attr(current_state: Dict[str, float], attr: str, mode="max"):
    """

    :param mode:
    :param current_state:
    :param attr:
    :return:
    """
    if mode == "min":
        return abs(current_state[attr] - 1) ** 2
    else:
        return current_state[attr] ** 2


def document_episode(nl, path: Path, reward_sum):
    """
       Create directory for current episode and command NetLogo to save model as csv
       :param reward_sum:
       :param nl: NetLogo-Session of environment
       :param path: Path of current environment
       :return:
       """
    path.mkdir(parents=True, exist_ok=True)
    # Get all directories to check, which episode this is
    dirs = glob(str(path) + "/E*.csv")
    current_episode = 1
    if dirs:
        last_episode = max(
            [int(re.findall("E(\d+)", dirs[i])[0]) for i in range(len(dirs))]
        )
        current_episode = last_episode + 1
    episode_path = str(path / f"E{current_episode}_{np.around(reward_sum, 8)}").replace("\\", "/")

    nl.command(f'export-world "{episode_path}.csv"')
