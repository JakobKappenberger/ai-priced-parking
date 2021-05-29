import argparse
import importlib
import math
import os
import pickle
from datetime import datetime

import ConfigSpace as cs
import numpy as np
from hpbandster.core.nameserver import NameServer, nic_name_to_host
from hpbandster.core.result import json_result_logger, logged_results_to_HBS_result
from hpbandster.core.worker import Worker
from hpbandster.optimizers import BOHB
from tensorforce import Runner, util


class TensorforceWorker(Worker):

    def __init__(
            self, *args, environment, num_episodes, base, runs_per_round, max_episode_timesteps=None,
            num_parallel=None, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.environment = environment
        self.max_episode_timesteps = max_episode_timesteps
        self.num_episodes = num_episodes
        self.base = base
        self.runs_per_round = runs_per_round
        self.num_parallel = num_parallel

    def compute(self, config_id, config, budget, working_directory):
        budget = math.log(budget, self.base)
        assert abs(budget - round(budget)) < util.epsilon
        budget = round(budget)
        assert budget < len(self.runs_per_round)
        num_runs = self.runs_per_round[budget]

        print(config)
        if config['entropy_regularization'] < 1e-5:
            entropy_regularization = 0.0
        else:
            entropy_regularization = config['entropy_regularization']

        agent = dict(
            agent='dqn', memory=50000, learning_rate=config['learning_rate'], batch_size=config['batch_size'],
            horizon=config['horizon'], discount=config['discount']
        )

        average_reward = list()
        final_reward = list()
        rewards = list()

        env_kwargs = {
            'timestamp': datetime.now().strftime('%y%m-%d-%H%M'),
            'reward_key': 'occupancy',
            'document': False
        }

        for n in range(num_runs):
            if self.num_parallel is None:
                runner = Runner(
                    agent=agent, environment=self.environment,
                    max_episode_timesteps=self.max_episode_timesteps, **env_kwargs
                )
                runner.run(num_episodes=self.num_episodes, use_tqdm=False)
            else:
                runner = Runner(
                    agent=agent, environment=self.environment,
                    max_episode_timesteps=self.max_episode_timesteps,
                    num_parallel=min(self.num_parallel, config['batch_size']),
                    remote='multiprocessing', **env_kwargs
                )
                runner.run(
                    num_episodes=self.num_episodes, batch_agent_calls=True, sync_episodes=True,
                    use_tqdm=False
                )
            runner.close()

            average_reward.append(float(np.mean(runner.episode_rewards, axis=0)))
            final_reward.append(float(np.mean(runner.episode_rewards[-20:], axis=0)))
            rewards.append(list(runner.episode_rewards))

        mean_average_reward = float(np.mean(average_reward, axis=0))
        mean_final_reward = float(np.mean(final_reward, axis=0))
        loss = -(mean_average_reward + mean_final_reward)

        return dict(loss=loss, info=dict(rewards=rewards))

    @staticmethod
    def get_configspace():
        configspace = cs.ConfigurationSpace()

        batch_size = cs.hyperparameters.UniformIntegerHyperparameter(
            name='batch_size', lower=1, upper=20, log=True
        )
        configspace.add_hyperparameter(hyperparameter=batch_size)

        learning_rate = cs.hyperparameters.UniformFloatHyperparameter(
            name='learning_rate', lower=1e-5, upper=1e-1, log=True
        )
        configspace.add_hyperparameter(hyperparameter=learning_rate)

        horizon = cs.hyperparameters.UniformIntegerHyperparameter(
            name='horizon', lower=1, upper=24, log=True
        )
        configspace.add_hyperparameter(hyperparameter=horizon)

        discount = cs.hyperparameters.UniformFloatHyperparameter(
            name='discount', lower=0.8, upper=1.0, log=True
        )
        configspace.add_hyperparameter(hyperparameter=discount)

        discount = cs.hyperparameters.UniformFloatHyperparameter(
            name='exploration ', lower=0.001, upper=0.2, log=True
        )
        configspace.add_hyperparameter(hyperparameter=discount)

        # < 1e-5: off (ln(3e-6) roughly 1/10 of ln(1e-5))
        entropy_regularization = cs.hyperparameters.UniformFloatHyperparameter(
            name='entropy_regularization', lower=3e-6, upper=1.0, log=True
        )
        configspace.add_hyperparameter(hyperparameter=entropy_regularization)

        return configspace


def main():
    parser = argparse.ArgumentParser(
        description='Tensorforce hyperparameter tuner, using BOHB optimizer (Bayesian Optimization '
                    'and Hyperband)'
    )
    # Environment arguments (from run.py)
    parser.add_argument(
        '-e', '--environment', type=str,
        help='Environment (name, configuration JSON file, or library module)'
    )
    parser.add_argument(
        '-l', '--level', type=str, default=None,
        help='Level or game id, like `CartPole-v1`, if supported'
    )
    parser.add_argument(
        '-m', '--max-episode-timesteps', type=int, default=None,
        help='Maximum number of timesteps per episode'
    )
    parser.add_argument(
        '--import-modules', type=str, default=None,
        help='Import comma-separated modules required for environment'
    )
    # Runner arguments (from run.py)
    parser.add_argument('-n', '--episodes', type=int, help='Number of episodes')
    parser.add_argument(
        '-p', '--num-parallel', type=int, default=None,
        help='Number of environment instances to execute in parallel'
    )
    # Tuner arguments
    parser.add_argument(
        '-r', '--runs-per-round', type=str, default='1,2,5,10',
        help='Comma-separated number of runs per optimization round, each with a successively '
             'smaller number of candidates'
    )
    parser.add_argument(
        '-s', '--selection-factor', type=int, default=3,
        help='Selection factor n, meaning that one out of n candidates in each round advances to '
             'the next optimization round'
    )
    parser.add_argument(
        '-i', '--num-iterations', type=int, default=1,
        help='Number of optimization iterations, each consisting of a series of optimization '
             'rounds with an increasingly reduced candidate pool'
    )
    parser.add_argument(
        '-d', '--directory', type=str, default='tuner', help='Output directory'
    )
    parser.add_argument(
        '--restore', type=str, default=None, help='Restore from given directory'
    )
    parser.add_argument('--id', type=str, default='worker', help='Unique worker id')
    args = parser.parse_args()

    if args.import_modules is not None:
        for module in args.import_modules.split(','):
            importlib.import_module(name=module)

    environment = dict(environment=args.environment)
    if args.level is not None:
        environment['level'] = args.level

    if False:
        host = nic_name_to_host(nic_name=None)
        port = 123
    else:
        host = 'localhost'
        port = None

    runs_per_round = tuple(int(x) for x in args.runs_per_round.split(','))
    print('Bayesian Optimization and Hyperband optimization')
    print(f'{args.num_iterations} iterations of each {len(runs_per_round)} rounds:')
    for n, num_runs in enumerate(runs_per_round, start=1):
        num_candidates = round(math.pow(args.selection_factor, len(runs_per_round) - n))
        print(f'round {n}: {num_candidates} candidates, each {num_runs} runs')
    print()

    server = NameServer(run_id=args.id, working_directory=args.directory, host=host, port=port)
    nameserver, nameserver_port = server.start()

    worker = TensorforceWorker(
        environment=environment, max_episode_timesteps=args.max_episode_timesteps,
        num_episodes=args.episodes, base=args.selection_factor, runs_per_round=runs_per_round,
        num_parallel=args.num_parallel, run_id=args.id, nameserver=nameserver,
        nameserver_port=nameserver_port, host=host
    )
    worker.run(background=True)

    if args.restore is None:
        previous_result = None
    else:
        previous_result = logged_results_to_HBS_result(directory=args.restore)

    result_logger = json_result_logger(directory=args.directory, overwrite=True)

    optimizer = BOHB(
        configspace=worker.get_configspace(), eta=args.selection_factor, min_budget=0.9,
        max_budget=math.pow(args.selection_factor, len(runs_per_round) - 1), run_id=args.id,
        working_directory=args.directory, nameserver=nameserver, nameserver_port=nameserver_port,
        host=host, result_logger=result_logger, previous_result=previous_result
    )
    # BOHB(configspace=None, eta=3, min_budget=0.01, max_budget=1, min_points_in_model=None,
    # top_n_percent=15, num_samples=64, random_fraction=1 / 3, bandwidth_factor=3,
    # min_bandwidth=1e-3, **kwargs)
    # Master(run_id, config_generator, working_directory='.', ping_interval=60,
    # nameserver='127.0.0.1', nameserver_port=None, host=None, shutdown_workers=True,
    # job_queue_sizes=(-1,0), dynamic_queue_size=True, logger=None, result_logger=None,
    # previous_result = None)
    # logger: logging.logger like object, the logger to output some (more or less meaningful)
    # information

    results = optimizer.run(n_iterations=args.num_iterations)
    # optimizer.run(n_iterations=1, min_n_workers=1, iteration_kwargs={})
    # min_n_workers: int, minimum number of workers before starting the run

    optimizer.shutdown(shutdown_workers=True)
    server.shutdown()

    with open(os.path.join(args.directory, 'results.pkl'), 'wb') as filehandle:
        pickle.dump(results, filehandle)

    print('Best found configuration: {}'.format(
        results.get_id2config_mapping()[results.get_incumbent_id()]['config']
    ))
    print('Runs:', results.get_runs_by_id(config_id=results.get_incumbent_id()))
    print('A total of {} unique configurations where sampled.'.format(
        len(results.get_id2config_mapping())
    ))
    print('A total of {} runs where executed.'.format(len(results.get_all_runs())))


if __name__ == '__main__':
    main()
