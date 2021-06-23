import sys
from argparse import ArgumentParser

sys.path.append("./external")

from experiment import Experiment


def add_bool_arg(parser, name, default=False):
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument('--' + name, dest=name, action='store_true')
    group.add_argument('--no-' + name, dest=name, action='store_false')
    parser.set_defaults(**{name: default})


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-p", "--num_parallel", type=int,
                        help="CPU cores to use")
    parser.add_argument("-a", "--agent", type=str,
                        help="Specification (JSON) of Agent to use")
    parser.add_argument('-n', '--episodes', type=int, help='Number of episodes')
    parser.add_argument('-r', '--reward_key', type=str, default='occupancy',
                        help='Reward function to use')
    add_bool_arg(parser, 'batch_agent_calls')
    add_bool_arg(parser, 'sync_episodes')
    add_bool_arg(parser, 'document', default=True)
    add_bool_arg(parser, 'adjust_free', default=True)
    parser.add_argument('-c', '--checkpoint', type=str, default=None,
                        help='Previous checkpoint to load')

    args = parser.parse_args()
    print(args)

    experiment = Experiment(agent=args.agent, num_episodes=args.episodes, batch_agent_calls=args.batch_agent_calls,
                            sync_episodes=args.sync_episodes, num_parallel=args.num_parallel,
                            reward_key=args.reward_key, document=args.document, adjust_free=args.adjust_free,
                            checkpoint=args.checkpoint, args=vars(args))
    experiment.run()
