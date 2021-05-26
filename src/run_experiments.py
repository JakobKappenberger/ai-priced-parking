from argparse import ArgumentParser
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
from tensorforce.execution import Runner

from custom_environment import CustomEnvironment
from experiment import Experiment


def main(num_parallel: int):
    """

    :param num_parallel:
    :return:
    """
    env_kwargs = {
        'timestamp': datetime.now().strftime('%y%m-%d-%H%M'),
        'reward_key': 'occupancy',
        'document': True
    }
    # Create appropriate number of environments
    if num_parallel > 1:
        runner = Runner(agent='agent.json', environment=CustomEnvironment, remote='multiprocessing',
                        num_parallel=num_parallel, max_episode_timesteps=500, **env_kwargs)
    else:
        runner = Runner(agent='agent.json', environment=CustomEnvironment,
                        max_episode_timesteps=500, **env_kwargs)

    runner.run(num_episodes=100, batch_agent_calls=False)

    # Accessing the metrics from runner
    rewards = np.asarray(runner.episode_rewards)
    episode_length = np.asarray(runner.episode_timesteps)

    # Close runner
    runner.close()

    # calculating the mean-reward per episode
    mean_reward = rewards / episode_length
    num_episodes = len(mean_reward)

    # plotting mean-reward over episodes
    f, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(20, 10))
    ax1.plot(range(num_episodes), mean_reward, linewidth=3)
    # plt.xticks(fontsize=15)
    ax1.set_ylabel('mean-reward', fontsize=22)
    ax1.grid(True)
    ax1.tick_params(axis="y", labelsize=15)
    # plotting episode length over episodes
    ax2.plot(range(num_episodes), rewards, linewidth=3)
    ax2.set_xlabel('# episodes', fontsize=22)
    ax2.set_ylabel('Reward', fontsize=22)
    ax2.tick_params(axis="y", labelsize=15)
    ax2.tick_params(axis="x", labelsize=15)
    ax2.grid(True)

    plt.show()

    print('number of episodes during training: ', len(rewards))
    print(rewards)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-p", "--num_parallel", type=int,
                        help="CPU cores to use")
    parser.add_argument("-a", "--agent", type=str,
                        help="Specification (JSON) of Agent to use")
    parser.add_argument('-n', '--episodes', type=int, help='Number of episodes')
    parser.add_argument('-r', '--reward_key', type=str, default='occupancy',
                        help='Reward function to use')
    parser.add_argument('-b', '--batch_agent_calls', type=bool, default=False,
                        help='Whether or not to call agent in batches')
    parser.add_argument('-d', '--document', type=bool, default=True,
                        help='Whether or not to document runs')
    args = parser.parse_args()
    experiment = Experiment(agent=args.agent, num_episodes=args.episodes,
                            batch_agent_calls=args.batch_agent_calls, num_parallel=args.num_parallel,
                            reward_key=args.reward_key, document=args.document)
    experiment.run()
    #main(num_parallel=num_parallel)
