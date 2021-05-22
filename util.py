# from environment import CustomEnvironment
import re
from pathlib import Path
from glob import glob

def occupancy_reward_function(env):
    """
    Rewards occupancy rates between 75% and 90%. Punishes deviations slightly.
    :param env: Environment-object
    :return:
    """
    reward = 0
    for c in env.colours:
        if 75 < env.current_state[f'{c}-lot occupancy'] < 90:
            reward += 5
        else:
            reward += -1

    return reward


def document_episode(env):
    """
    Create directory for current episode and command NetLogo to save model as csv
    :param env:
    :return:
    """
    Path(env.path).mkdir(parents=True, exist_ok=True)
    # Get all directories to check, which Episode this is
    dirs = glob(env.path + "/*")
    current_episode = 1
    if dirs:
        last_episode = max([int(re.findall("E(\d+)", dirs[i])[0]) for i in range(len(dirs))])
        print(last_episode)
        current_episode = last_episode + 1
    episode_path = env.path + f"/E{current_episode}"

    # # Check if directory exists
    # Path(self.path).mkdir(parents=True, exist_ok=True)
    # if self.episode > 1:
    #     self.episode += self.episode
    # episode_path = self.path + f"/E{self.episode}"
    # Path(episode_path).mkdir(parents=True, exist_ok=True)
    env.nl.command(f'export-world "{episode_path}.csv"')
