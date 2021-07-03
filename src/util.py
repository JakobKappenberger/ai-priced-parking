# from environment import CustomEnvironment
import re
from glob import glob
from pathlib import Path
from typing import List, Dict

import numpy as np


def occupancy_reward_function(colours: List[str], current_state: Dict[str, float]):
    """
    Rewards occupancy rates between 75% and 90%. Punishes deviations as the squared deviation from the target range.
    :param current_state:
    :param colours:
    :return:
    """
    reward = 0
    for c in colours:
        if current_state[f'{c}-lot occupancy'] <= 0.825:
            reward += 1 - (abs(current_state[f'{c}-lot occupancy'] - 0.825) / 0.825) ** 0.4
        else:
            value = 1 - (abs(current_state[f'{c}-lot occupancy'] - 0.825) / 0.825) ** 0.4
            min_value = 1 - (abs(1 - 0.825) / 0.825) ** 0.4
            max_value = 1 - (abs(0.825 - 0.825) / 0.825) ** 0.4
            max_distance = max_value - min_value
            actual_distance = value - min_value
            reward += actual_distance / max_distance
        # if 0.75 < current_state[f'{c}-lot occupancy'] < 0.90:
        #     reward += 0.25
        # else:
        #     reward -= 0.25

    return reward / len(colours)


def n_cars_reward_function(colours: List[str], current_state: Dict[str, float]):
    """

    :param colours:
    :param current_state:
    :return:
    """
    return minimize_attr(current_state, "n_cars")

def minimize_attr(current_state: Dict[str, float], attr: str):
    """

    :param current_state:
    :param attr:
    :return:
    """
    return abs(current_state[attr] - 1) ** 2


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
