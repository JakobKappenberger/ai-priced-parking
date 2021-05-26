from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from tensorforce.execution import Runner

from custom_environment import CustomEnvironment


class Experiment:
    def __init__(self, agent: str, num_episodes: int, batch_agent_calls: bool, document: bool = True,
                 num_parallel: int = 1, reward_key: str = 'occupancy'):
        """

        :param agent:
        :param num_episodes:
        :param batch_agent_calls:
        :param document:
        :param num_parallel:
        :param reward_key:
        """
        self.num_episodes = num_episodes
        self.batch_agent_calls = batch_agent_calls
        self.timestamp = datetime.now().strftime('%y%m-%d-%H%M')
        self.path = Path(".").absolute().parent / "Experiments" / self.timestamp
        env_kwargs = {
            'timestamp': self.timestamp,
            'reward_key': reward_key,
            'document': document
        }
        # Create appropriate number of environments
        if num_parallel > 1:
            self.runner = Runner(agent=agent, environment=CustomEnvironment, remote='multiprocessing',
                                 num_parallel=num_parallel, max_episode_timesteps=24, **env_kwargs)
        else:
            self.runner = Runner(agent=agent, environment=CustomEnvironment,
                                 max_episode_timesteps=24, **env_kwargs)
            self.batch_agent_calls = False

    def run(self):
        """

        :return:
        """
        self.runner.run(num_episodes=self.num_episodes, batch_agent_calls=self.batch_agent_calls)

        results_dict = dict()
        # Accessing the metrics from runner
        rewards = np.asarray(self.runner.episode_rewards)
        episode_length = np.asarray(self.runner.episode_timesteps)
        mean_reward = rewards / episode_length
        metrics_df = pd.DataFrame.from_dict({'rewards': rewards, 'episode_length': episode_length,
                                             'mean_reward': mean_reward})
        metrics_df.to_csv(str(self.path / 'result.csv'))

        # plotting mean-reward over episodes
        fig, ax = plt.subplots(figsize=(20, 10))
        ax.plot(range(len(mean_reward)), mean_reward, linewidth=3)
        # plt.xticks(fontsize=15)
        ax.set_ylabel('Mean Reward', fontsize=22)
        ax.set_xlabel('# Episodes', fontsize=22)
        ax.grid(True)
        ax.tick_params(axis="y", labelsize=15)
        ax.tick_params(axis="x", labelsize=15)

        fig.savefig(
            str(self.path / 'reward_plot.pdf'),
            dpi=300)

        # Close runner
        self.runner.close()
