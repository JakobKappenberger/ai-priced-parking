import json
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from cmcrameri import cm

from custom_environment import CustomEnvironment
from external.tensorforce.execution import Runner

sns.set_style('dark')
sns.set_context('paper')


class Experiment:
    def __init__(self, agent: str,
                 num_episodes: int,
                 args,
                 batch_agent_calls: bool = False,
                 sync_episodes: bool = False,
                 document: bool = True,
                 adjust_free: bool = False,
                 num_parallel: int = 1,
                 reward_key: str = 'occupancy',
                 checkpoint: str = None):
        """
        Class to run individual experiments.
        :param agent: Agent specification (Path to JSON-file)
        :param num_episodes:
        :param batch_agent_calls:
        :param document: Boolean if model outputs are to be saved
        :param num_parallel: number of environments to run in parallel
        :param reward_key: key to choose reward function
        """
        self.num_episodes = num_episodes
        self.batch_agent_calls = batch_agent_calls
        self.sync_episodes = sync_episodes
        if checkpoint is not None:
            self.resume_checkpoint = True
            self.timestamp = checkpoint
        else:
            self.resume_checkpoint = False
            self.timestamp = datetime.now().strftime('%y%m-%d-%H%M')
        self.outpath = Path(".").absolute().parent / "Experiments" / self.timestamp
        # Create directory (if it does not exist yet)
        self.outpath.mkdir(parents=True, exist_ok=True)
        env_kwargs = {
            'timestamp': self.timestamp,
            'reward_key': reward_key,
            'document': document,
            'adjust_free': adjust_free
        }

        if self.resume_checkpoint:
            agent = dict()
            agent["directory"] = str(self.outpath / 'model-checkpoints')
            agent["format"] = "checkpoint"
        else:
            # Load json file for agent init
            with open(agent, 'r') as fp:
                agent = json.load(fp=fp)
            # Update checkpoint path
            agent['saver']['directory'] = str(self.outpath / 'model-checkpoints')

            # Document Config
            args['agent'] = agent
            with open(str(self.outpath / 'config.txt'), 'w') as outfile:
                json.dump(args, outfile)

        # Create appropriate number of environments
        if num_parallel > 1:
            self.runner = Runner(agent=agent, environment=CustomEnvironment, remote='multiprocessing',
                                 num_parallel=num_parallel, max_episode_timesteps=24, **env_kwargs)
        else:
            self.runner = Runner(agent=agent, environment=CustomEnvironment,
                                 max_episode_timesteps=24, **env_kwargs)
            self.batch_agent_calls = False
            self.sync_episodes = False

    def run(self):
        """
        Runs actual experiments and saves results.
        :return:
        """
        self.runner.run(num_episodes=self.num_episodes, batch_agent_calls=self.batch_agent_calls,
                        sync_episodes=self.sync_episodes, save_best_agent=str(self.outpath / 'best_agent'))

        results_dict = dict()
        # Accessing the metrics from runner
        rewards = np.asarray(self.runner.episode_returns)
        episode_length = np.asarray(self.runner.episode_timesteps)
        mean_reward = rewards / episode_length
        metrics_df = pd.DataFrame.from_dict({'rewards': rewards, 'episode_length': episode_length,
                                             'mean_reward': mean_reward})

        csv_path = self.outpath / 'result.csv'
        i = 1
        # Check if results file already exists
        while csv_path.is_file():
            csv_path = self.outpath / f'result ({i}).csv'
            i += 1
        metrics_df.to_csv(str(csv_path))

        # plotting mean-reward over episodes
        fig, ax = plt.subplots(figsize=(20, 10), constrained_layout=True)
        ax.plot(range(len(mean_reward)), metrics_df.mean_reward, linewidth=5, color=cm.bamako(0))
        rolling_average = metrics_df.mean_reward.rolling(10).mean()
        ax.plot(range(len(rolling_average)), rolling_average, linewidth=3, color=cm.bamako(1.0))
        ax.set_ylabel('Mean Reward per Episode', fontsize=30)
        ax.set_xlabel('# Episodes', fontsize=30)
        ax.grid(True)
        ax.tick_params(axis="y", labelsize=25)
        ax.tick_params(axis="x", labelsize=25)

        fig.savefig(
            str(self.outpath / 'reward_plot.pdf'),
            dpi=300)

        # Close runner
        self.runner.close()
