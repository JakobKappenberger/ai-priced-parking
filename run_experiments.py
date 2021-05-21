import matplotlib.pyplot as plt
import numpy as np
from tensorforce.execution import Runner

from custom_environment import CustomEnvironment


def main():
    # create and train the agent
    runner = Runner(agent='agent.json', environment=CustomEnvironment, max_episode_timesteps=500,
                    remote="multiprocessing", num_parallel=2)
    runner.run(num_episodes=50)

    # Accessing the metrics from runner
    rewards = np.asarray(runner.episode_rewards)
    episode_length = np.asarray(runner.episode_timesteps)

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
    main()
