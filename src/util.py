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
        # reward += 1 - (abs(current_state[f'{c}-lot occupancy'] - 0.825) / 0.825) ** 0.4
        if 0.75 < current_state[f'{c}-lot occupancy'] < 0.90:
            reward += 0.25
        else:
            reward -= 0.25

    return reward


def n_cars_reward_function(colours: List[str], current_state: Dict[str, float]):
    """

    :param colours:
    :param current_state:
    :return:
    """
    return abs(current_state['n_cars'] - 1)


def document_episode(nl, path: Path, reward_sum):
    """
       Create directory for current episode and command NetLogo to save model as csv
       :param reward_sum:
       :param nl: NetLogo-Session of environment
       :param path: Path of current environment
       :return:
       """
    path.mkdir(parents=True, exist_ok=True)
    # Get all directories to check, which Episode this is
    dirs = glob(str(path) + "/E*.csv")
    current_episode = 1
    if dirs:
        last_episode = max(
            [int(re.findall("E(\d+)", dirs[i])[0]) for i in range(len(dirs))]
        )
        current_episode = last_episode + 1
    episode_path = str(path / f"E{current_episode}_{np.around(reward_sum, 2)}").replace("\\", "/")

    # # Check if directory exists
    # Path(self.path).mkdir(parents=True, exist_ok=True)
    # if self.episode > 1:
    #     self.episode += self.episode
    # episode_path = self.path + f"/E{self.episode}"
    # Path(episode_path).mkdir(parents=True, exist_ok=True)
    nl.command(f'export-world "{episode_path}.csv"')
