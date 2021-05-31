from pathlib import Path

import numpy as np
import pyNetLogo
from tensorforce.environments import Environment

from util import occupancy_reward_function, document_episode

COLOURS = ['yellow', 'orange', 'green', 'blue']
REWARD_FUNCTIONS = {
    'occupancy': occupancy_reward_function
}


class CustomEnvironment(Environment):
    def __init__(self, timestamp: str, reward_key: str, document: bool = False):
        """
        Wrapper-Class to interact with NetLogo parking Simulations.
        :param timestamp:
        :param reward_key: Key to choose reward function
        :param document: Boolean
        """
        super().__init__()
        self.timestamp = timestamp
        self.path = Path(".").absolute().parent / "Experiments" / self.timestamp
        self.finished = False
        self.episode_end = False
        self.document = document
        self.reward_function = REWARD_FUNCTIONS[reward_key]
        # Connect to NetLogo
        self.nl = pyNetLogo.NetLogoLink(gui=False)
        self.nl.load_model('Model.nlogo')
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
            return dict(type="float", shape=(12,), min_value=0)
        else:
            return dict(type="float", shape=(11,), min_value=0)

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
        if terminal and self.document:
            document_episode(self.nl, self.path)
        return next_state, terminal, reward

    def compute_step(self, actions):
        """
        Moves simulation one time step forward and records current state.
        :param actions: actions to be taken in next time step
        :return:
        """
        # Move simulation forward
        self.nl.repeat_command("go", self.temporal_resolution / 2)

        # Adjust prices and query state
        new_state = self.adjust_prices(actions)

        return new_state

    def adjust_prices(self, actions):
        """
        Adjust prices in the simulation according to the actions taken by the agent.
        :param actions:
        :return:
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
        Query current state of simulation.
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

        state = [np.around(s, 2) for s in list(self.current_state.values())]
        return state

    def terminal(self):
        """
        Determine whether episode ended (equvialent of 12 hours have passed) or finishing criteria
        (minimum number of cars) is reached
        :return:
        """
        self.episode_end = self.current_state['ticks'] >= self.temporal_resolution * 12
        self.finished = self.current_state['n_cars'] < 100

        return self.finished or self.episode_end

    def reward(self):
        """
        Return the adequate reward function (defined in util.py)
        :return:
        """

        return self.reward_function(colours=self.colours, current_state=self.current_state)
