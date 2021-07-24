import json
import platform
from pathlib import Path

import numpy as np
import pyNetLogo

from external.tensorforce.environments import Environment
from util import occupancy_reward_function, n_cars_reward_function, social_reward_function, speed_reward_function, \
    composite_reward_function, document_episode

COLOURS = ['yellow', 'green', 'teal', 'blue']
REWARD_FUNCTIONS = {
    'occupancy': occupancy_reward_function,
    'n_cars': n_cars_reward_function,
    'social': social_reward_function,
    'speed': speed_reward_function,
    'composite': composite_reward_function
}


class CustomEnvironment(Environment):
    def __init__(self,
                 timestamp: str,
                 reward_key: str,
                 document: bool = False,
                 adjust_free: bool = False,
                 model_size: str = 'training'):
        """
        Wrapper-Class to interact with NetLogo parking Simulations.
        :param timestamp: Timestamp of episode.
        :param reward_key: Key to choose reward function
        :param document: Boolean to control whether individual episode results are saved.
        :param adjust_free: Boolean to control whether prices are adjusted freely or incrementally
        :param model_size: Model size to run experiments with, either "training" or "evaluation".
        """
        super().__init__()
        self.timestamp = timestamp
        self.outpath = Path(".").absolute().parent / "Experiments" / self.timestamp
        self.finished = False
        self.episode_end = False
        self.document = document
        self.adjust_free = adjust_free
        self.reward_function = REWARD_FUNCTIONS[reward_key]
        self.reward_sum = 0
        # Load model parameters
        with open('model_config.json', 'r') as fp:
            model_config = json.load(fp=fp)
        # Connect to NetLogo
        if platform.system() == 'Linux':
            self.nl = pyNetLogo.NetLogoLink(gui=False, netlogo_home="./external/NetLogo 6.2.0", netlogo_version="6.2")
        else:
            self.nl = pyNetLogo.NetLogoLink(gui=False)
        self.nl.load_model('Train_Model.nlogo')
        # Set model size
        self.set_model_size(model_config, model_size)
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

    def set_model_size(self, model_config, model_size):
        """
        Set NetLogo model to the appropriate size.
        :param model_config: Config dict containing grid size as well as number of cars and garages.
        :param model_size: Model size to run experiments with, either "training" or "evaluation".
        :return:
        """
        print(f"Configuring model size for {model_size}")
        max_x_cor = model_config[model_size]['max_x_cor']
        max_y_cor = model_config[model_size]['max_y_cor']
        self.nl.command(f'resize-world {-max_x_cor} {max_x_cor} {-max_y_cor} {max_y_cor}')
        self.nl.command(f'set num-cars {model_config[model_size]["num_cars"]}')
        self.nl.command(f'set num-garages {model_config[model_size]["num_garages"]}')

    def states(self):
        if self.n_garages > 0:
            return dict(type="float", shape=(15,), min_value=0)
        else:
            return dict(type="float", shape=(14,), min_value=0)

    def actions(self):
        if self.adjust_free:
            return {
                COLOURS[0]: dict(type="int", num_values=21),
                COLOURS[1]: dict(type="int", num_values=21),
                COLOURS[2]: dict(type="int", num_values=21),
                COLOURS[3]: dict(type="int", num_values=21)
            }
        else:
            return {
                COLOURS[0]: dict(type="int", num_values=3),
                COLOURS[1]: dict(type="int", num_values=3),
                COLOURS[2]: dict(type="int", num_values=3),
                COLOURS[3]: dict(type="int", num_values=3)
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
        # Turn baseline pricing mechanism off
        self.nl.command('set dynamic-pricing-baseline false')
        # Record data
        self.nl.command("ask one-of cars [record-data]")
        self.finished = False
        self.episode_end = False
        self.reward_sum = 0
        self.current_state['ticks'] = self.nl.report("ticks")
        self.current_state['n_cars'] = float(self.nl.report("n-cars"))
        self.current_state['overall_occupancy'] = self.nl.report("global-occupancy")

        state = self.get_state()
        return state

    def execute(self, actions):
        next_state = self.compute_step(actions)
        terminal = self.terminal()
        reward = self.reward()
        self.reward_sum += reward
        if terminal and self.document:
            document_episode(self.nl, self.outpath, self.reward_sum)
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
        if self.adjust_free:
            new_state = self.adjust_prices_free(actions)
        else:
            new_state = self.adjust_prices_step(actions)

        return new_state

    def adjust_prices_free(self, actions):
        """
        Adjust prices freely in the interval from 0 to 10 in the simulation according to the actions taken by the agent.
        :param actions:
        :return:
        """
        for c in actions.keys():
            new_fee = actions[c] / 2
            self.nl.command(f"change-fee-free {c}-lot {new_fee}")

        return self.get_state()

    def adjust_prices_step(self, actions):
        """
        Adjust prices incrementally in the simulation according to the actions taken by the agent.
        :param actions:
        :return:
        """
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
        self.current_state['city_income'] = self.nl.report("city-income")
        self.current_state['mean_speed'] = self.nl.report("mean-speed")
        self.current_state['income_entropy'] = self.nl.report("income-entropy")

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
        Determine whether episode ended (equivalent of 12 hours have passed) or finishing criteria
        (minimum number of cars) is reached
        :return:
        """
        self.episode_end = self.current_state['ticks'] >= self.temporal_resolution * 12
        self.finished = self.current_state['n_cars'] < 0.1

        return self.finished or self.episode_end

    def reward(self):
        """
        Return the adequate reward function (defined in util.py)
        :return:
        """
        return self.reward_function(colours=self.colours, current_state=self.current_state)
