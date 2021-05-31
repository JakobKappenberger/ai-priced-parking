from argparse import ArgumentParser

from experiment import Experiment

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
    parser.add_argument('-s', '--sync_episodes', type=bool, default=False,
                        help='Whether or not to sync episodes when executing in parallel')
    parser.add_argument('-d', '--document', type=bool, default=True,
                        help='Whether or not to document runs')
    args = parser.parse_args()
    experiment = Experiment(agent=args.agent, num_episodes=args.episodes,
                            batch_agent_calls=args.batch_agent_calls, sync_episodes=args.sync_episodes,
                            num_parallel=args.num_parallel, reward_key=args.reward_key, document=args.document)
    experiment.run()