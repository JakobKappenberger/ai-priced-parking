# from environment import CustomEnvironment
import re
from glob import glob
from pathlib import Path
from typing import List, Dict


def occupancy_reward_function(colours: List[str], current_state: Dict[str, float]):
    """
    Rewards occupancy rates between 75% and 90%. Punishes deviations as the squared deviation from the target range.
    :param current_state:
    :param colours:
    :return:
    """
    reward = 0
    for c in colours:
        if 75 < current_state[f'{c}-lot occupancy'] < 90:
            reward += 25
        elif current_state[f'{c}-lot occupancy'] <= 75:
            reward -= (current_state[f'{c}-lot occupancy'] - 75) ** 2
        elif current_state[f'{c}-lot occupancy'] >= 90:
            reward -= (current_state[f'{c}-lot occupancy'] - 90) ** 2

    return reward


def document_episode(nl, path):
    """
    Create directory for current episode and command NetLogo to save model as csv
    :param nl: NetLogo-Session of environment
    :param path: Path of current environment
    :return:
    """
    Path(path).mkdir(parents=True, exist_ok=True)
    # Get all directories to check, which Episode this is
    dirs = glob(path + "/*")
    current_episode = 1
    if dirs:
        last_episode = max([int(re.findall("E(\d+)", dirs[i])[0]) for i in range(len(dirs))])
        current_episode = last_episode + 1
    episode_path = path + f"/E{current_episode}"

    # # Check if directory exists
    # Path(self.path).mkdir(parents=True, exist_ok=True)
    # if self.episode > 1:
    #     self.episode += self.episode
    # episode_path = self.path + f"/E{self.episode}"
    # Path(episode_path).mkdir(parents=True, exist_ok=True)
    nl.command(f'export-world "{episode_path}.csv"')
