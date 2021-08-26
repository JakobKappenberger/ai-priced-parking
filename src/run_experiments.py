import sys
from argparse import ArgumentParser

from util import add_bool_arg

sys.path.append("./external")

from experiment import Experiment

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("agent", type=str,
                        help="Specification (JSON) of Agent to use")
    parser.add_argument('episodes', type=int, help='Number of episodes')
    parser.add_argument("-p", "--num_parallel", type=int, default=1,
                        help="CPU cores to use")
    parser.add_argument('-r', '--reward_key', type=str, default='occupancy',
                        help='Reward function to use')
    parser.add_argument('-c', '--checkpoint', type=str, default=None,
                        help='Previous checkpoint to load')
    parser.add_argument('-m', '--model_size', type=str, default='training', choices=['training', 'evaluation'],
                        help='Control which model size to size')
    parser.add_argument('-np', '--nl_path', type=str, default=None,
                        help='Path to NetLogo directory (for Linux Users)')
    add_bool_arg(parser, 'batch_agent_calls')
    add_bool_arg(parser, 'sync_episodes')
    add_bool_arg(parser, 'document', default=True)
    add_bool_arg(parser, 'adjust_free', default=True)
    add_bool_arg(parser, 'eval', default=False)
    add_bool_arg(parser, 'zip', default=False)
    add_bool_arg(parser, 'gui', default=False)

    args = parser.parse_args()
    print(f" Experiment called with arguments: {vars(args)}")

    experiment = Experiment(agent=args.agent, num_episodes=args.episodes, batch_agent_calls=args.batch_agent_calls,
                            sync_episodes=args.sync_episodes, num_parallel=args.num_parallel,
                            reward_key=args.reward_key, document=args.document, adjust_free=args.adjust_free,
                            checkpoint=args.checkpoint, eval=args.eval, zip=args.zip, model_size=args.model_size,
                            nl_path=args.nl_path, gui=args.gui, args=vars(args))
    experiment.run()