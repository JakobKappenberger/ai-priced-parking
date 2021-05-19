from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pyNetLogo
from tensorforce.environments import Environment
from tensorforce.execution import Runner

from util import occupancy_reward_function

COLOURS = ['yellow', 'orange', 'green', 'blue']
TIMESTAMP = datetime.now().strftime('%y%m-%d%H-%M')


class CustomEnvironment(Environment):

    def __init__(self):
        super().__init__()
        self.path = "./Experiments/" + TIMESTAMP
        self.finished = False
        self.episode_end = False
        # Episode Counter
        self.episode = 1
        self.nl = pyNetLogo.NetLogoLink(gui=True)
        self.nl.load_model('.Social_Simulation_Seminar_Model.nlogo')
        self.nl.command('setup')
        # Disable rendering of view
        self.nl.command('no-display')
        # Turn baseline pricing mechanism off
        self.nl.command('set dynamic-pricing-baseline false')
        # Record data
        self.nl.command("ask one-of cars [record-data]")
        # Save current state in dict
        self.current_state = dict()
        self.current_state['ticks'] = self.nl.report("ticks")
        self.current_state['n_cars'] = float(self.nl.report("n-cars"))
        self.current_state['overall_occupancy'] = self.nl.report("global-occupancy")

        # General information about model
        self.temporal_resolution = self.nl.report("temporal-resolution")
        self.n_garages = self.nl.report("num-garages")
        self.colours = COLOURS

    def states(self):
        if self.n_garages > 0:
            return dict(type="float", shape=(12,))
        else:
            return dict(type="float", shape=(11,))

    def actions(self):
        return {
            "yellow": dict(type="int", num_values=3),
            "orange": dict(type="int", num_values=3),
            "green": dict(type="int", num_values=3),
            "blue": dict(type="int", num_values=3)
        }

    # Optional: should only be defined if environment has a natural fixed
    # maximum episode length; otherwise specify maximum number of training
    # timesteps via Environment.create(..., max_episode_timesteps=???)
    def max_episode_timesteps(self):
        return super().max_episode_timesteps()

    # Optional additional steps to close environment
    def close(self):
        self.nl.kill_workspace()
        super().close()

    def reset(self):
        self.nl.command('setup')
        state = self.get_state()
        return state

    def execute(self, actions):
        next_state = self.compute_step(actions)
        terminal = self.terminal()
        reward = self.reward()
        if terminal:
            self.document_episode()
        return next_state, terminal, reward

    def compute_step(self, actions):
        """
        """
        # Move simulation forward
        self.nl.repeat_command("go", self.temporal_resolution / 2)

        # Adjust prices and query state
        new_state = self.adjust_prices(actions)

        return new_state

    def adjust_prices(self, actions):
        """
        """
        # print(actions)
        for c in actions.keys():
            c_action = actions[c]
            if c_action == 0:
                self.nl.command(f"change-fee {c}-lot -0.5")
            elif c_action == 1:
                continue
            elif c_action == 2:
                self.nl.command(f"change-fee {c}-lot 0.5")

        return self.get_state()

    def get_state(self):
        """
        """
        # Update view in NetLogo once
        self.nl.command('display')
        self.nl.command('no-display')
        # Update globals
        self.nl.command("ask one-of cars [record-data]")
        self.current_state['ticks'] = self.nl.report("ticks")
        self.current_state['n_cars'] = float(self.nl.report("n-cars"))
        self.current_state['overall_occupancy'] = self.nl.report("global-occupancy")

        # Append fees and current occupation to state
        for c in self.colours:
            self.current_state[f'{c}-lot fee'] = self.nl.report(f"{c}-lot-current-fee")
            self.current_state[f'{c}-lot occupancy'] = self.nl.report(f"{c}-lot-current-occup")

        if self.n_garages > 0:
            self.current_state['garages occupancy'] = self.nl.report("garages-current-occup")

        state = list(self.current_state.values())
        return state

    def terminal(self):
        self.episode_end = self.current_state['ticks'] >= self.temporal_resolution * 12
        self.finished = self.current_state['n_cars'] < 100

        return self.finished or self.episode_end

    def reward(self):
        """

        :return:
        """

        return occupancy_reward_function(self)

    def document_episode(self):
        """

        :return:
        """
        # Path(self.path).mkdir(parents=True, exist_ok=True)
        # # Get all directories to check, which Episode this is
        # dirs = glob(self.path + "/*")
        # current_episode = 1
        # if dirs:
        #     last_episode = max([int(re.findall("E(\d+)", dirs[i])[0]) for i in range(len(dirs))])
        #     print(last_episode)
        #     current_episode = last_episode + 1
        # episode_path = self.path + f"/E{current_episode}"
        # Path(episode_path).mkdir(parents=True, exist_ok=True)

        # Check if directory exists
        Path(self.path).mkdir(parents=True, exist_ok=True)
        if self.episode > 1:
            self.episode += self.episode
        episode_path = self.path + f"/E{self.episode}"
        Path(episode_path).mkdir(parents=True, exist_ok=True)
        self.nl.command(f'export-world "{episode_path}/nl_model.csv"')


if __name__ == "__main__":
    # envs = Environment.create(
    #     environment=CustomEnvironment, max_episode_timesteps=100, remote="multiprocessing"
    # )
    #
    # agent = Agent.create(
    #     agent='ppo', environment=envs, batch_size=10, learning_rate=1e-3
    # )
    agent_dict = {
        "agent": "ppo",
        "optimizer": {
            "learning_rate": 1e-3
        },
        "max_episode_timesteps": 100,
        "batch-size": 10
    }

    # create and train the agent
    runner = Runner(agent='agent.json', environment=CustomEnvironment, max_episode_timesteps=500,
                    remote="multiprocessing", num_parallel=4)
    runner.run(num_episodes=50)

    # accesing the metrics from runner
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

    # Close agent and environment
    #agent.close()
    # environment.close()

    # # Train for 100 episodes
    # for _ in range(50):
    #     states = environment.reset()
    #     terminal = False
    #     while not terminal:
    #         actions = agent.act(states=states)
    #         states, terminal, reward = environment.execute(actions=actions)
    #         agent.observe(terminal=terminal, reward=reward)
