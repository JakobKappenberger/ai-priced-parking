import matplotlib.pyplot as plt
import numpy as np
import pyNetLogo
from tensorforce.agents import Agent
from tensorforce.environments import Environment
from tensorforce.execution import Runner

class CustomEnvironment(Environment):

    def __init__(self):
        super().__init__()
        self.finished = False
        self.episode_end = False
        self.nl = pyNetLogo.NetLogoLink(gui=True)
        self.nl.load_model('.Social_Simulation_Seminar_Model.nlogo')
        self.nl.command('setup')
        # disable rendering of view
        self.nl.command('no-display')
        # Turn baseline pricing mechanism off
        self.nl.command('set dynamic-pricing-baseline false')
        # Record data
        self.nl.command("ask one-of cars [record-data]")
        self.ticks = self.nl.report("ticks")  #
        self.temporal_resolution = self.nl.report("temporal-resolution")
        self.n_garages = self.nl.report("num-garages")
        self.n_cars = float(self.nl.report("n-cars"))
        self.occupancy = self.nl.report("global-occupancy")

    def states(self):
        if self.n_garages > 0:
            return dict(type="float", shape=(11,))
        else:
            return dict(type="float", shape=(10,))

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
        #print(actions)
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
        state = []
        # Update view in NetLogo once
        self.nl.command('display')
        self.nl.command('no-display')
        # Update globals
        self.nl.command("ask one-of cars [record-data]")
        self.ticks = self.nl.report("ticks")  #
        self.n_cars = float(self.nl.report("n-cars"))
        state.append(self.n_cars)
        self.occupancy = self.nl.report("global-occupancy")
        state.append(self.occupancy)

        # Append fees and current occupation to state
        for c in ['yellow', 'orange', 'green', 'blue']:
            state.append(self.nl.report(f"{c}-lot-current-fee"))
            state.append(self.nl.report(f"{c}-lot-current-occup"))

        if self.n_garages > 0:
            state.append(self.nl.report("garages-current-occup"))

        return state

    def terminal(self):
        self.episode_end = self.ticks >= self.temporal_resolution * 12
        self.finished = self.n_cars < 300

        return self.finished or self.episode_end

    def reward(self):
        if 0.75 < self.occupancy < 0.85:
            reward = 5
        else:
            reward = -1
        return reward


if __name__ == "__main__":
    environment = Environment.create(
        environment=CustomEnvironment, max_episode_timesteps=100
    )

    agent = Agent.create(
        agent='ppo', environment=environment, batch_size=10, learning_rate=1e-3
    )

    # create and train the agent
    runner = Runner(agent=agent, environment=environment)
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
    ax2.plot(range(num_episodes), episode_length, linewidth=3)
    ax2.set_xlabel('# episodes', fontsize=22)
    ax2.set_ylabel('episode-length', fontsize=22)
    ax2.tick_params(axis="y", labelsize=15)
    ax2.tick_params(axis="x", labelsize=15)
    ax2.grid(True)

    plt.show()

    print('number of episodes during training: ', len(rewards))
    print(rewards)

    # # Train for 100 episodes
    # for _ in range(50):
    #     states = environment.reset()
    #     terminal = False
    #     while not terminal:
    #         actions = agent.act(states=states)
    #         states, terminal, reward = environment.execute(actions=actions)
    #         agent.observe(terminal=terminal, reward=reward)
