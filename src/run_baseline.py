import platform
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pyNetLogo
from tqdm import trange

from util import document_episode, label_episodes

COLOURS = ['yellow', 'green', 'teal', 'blue']


def run_baseline(num_episodes: int, num_cars: int = 525, max_x_cor: int = 45, max_y_cor: int = 41,
                 num_garages: int = 3):
    """

    :param num_episodes:
    :param num_cars:
    :param max_x_cor:
    :param max_y_cor:
    :param num_garages:
    :return:
    """
    timestamp = datetime.now().strftime('%y%m-%d-%H%M')
    outpath = Path(".").absolute().parent / "Experiments/Baseline" / timestamp
    # Connect to NetLogo
    if platform.system() == 'Linux':
        nl = pyNetLogo.NetLogoLink(gui=False, netlogo_home="./external/NetLogo 6.2.0", netlogo_version="6.2")
    else:
        nl = pyNetLogo.NetLogoLink(gui=False)
    nl.load_model('Train_Model.nlogo')
    nl.command(f'resize-world {-max_x_cor} {max_x_cor} {-max_y_cor} {max_y_cor}')
    nl.command(f'set num-cars {num_cars}')
    nl.command(f'set num-garages {num_garages}')

    traffic_counter = []
    scores = [0] * num_episodes

    for i in trange(num_episodes):
        nl.command('setup')
        # Disable rendering of view
        nl.command('no-display')
        nl.command("ask one-of cars [record-data]")
        for _ in range(24):
            nl.repeat_command("go", 900)
            for c in COLOURS:
                occup = nl.report(f"{c}-lot-current-occup")
                if 0.75 < occup < 0.9:
                    scores[i] += 0.25
        document_episode(nl=nl, path=outpath, reward_sum=scores[i])
        traffic_counter.append(nl.report("traffic-counter"))

    print(traffic_counter)
    print(np.mean(traffic_counter))
    nl.kill_workspace()
    metrics_df = pd.DataFrame(scores, columns=['rewards'])
    label_episodes(outpath, metrics_df, 'standard')


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument('-n', '--episodes', type=int, help='Number of episodes')
    parser.add_argument('-c', '--num_cars', type=int, help='Number of Cars', default=525)
    parser.add_argument('-g', '--num_garages', type=int, help='Number of Garages', default=3)

    parser.add_argument('-x', '--max_x_cor', type=int, help='Size of Grid (X)', default=45)
    parser.add_argument('-y', '--max_y_cor', type=int, help='Size of Grid (Y)', default=41)

    args = parser.parse_args()
    print(f" Baseline called with arguments: {vars(args)}")

    run_baseline(num_episodes=args.episodes, num_cars=args.num_cars, max_x_cor=args.max_x_cor, max_y_cor=args.max_y_cor,
                 num_garages=args.num_garages)
