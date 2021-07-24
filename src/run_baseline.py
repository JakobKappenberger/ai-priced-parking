import json
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


def run_baseline(num_episodes: int, model_size: str = "evaluation"):
    """
    Runs baseline experiments and save results.
    :param num_episodes: Number of episodes to run.
    :param model_size: Model size to run experiments with, either "training" or "evaluation".
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
    # Load model parameters
    with open('model_config.json', 'r') as fp:
        model_config = json.load(fp=fp)

    print(f"Configuring model size for {model_size}")
    max_x_cor = model_config[model_size]['max_x_cor']
    max_y_cor = model_config[model_size]['max_y_cor']
    nl.command(f'resize-world {-max_x_cor} {max_x_cor} {-max_y_cor} {max_y_cor}')
    nl.command(f'set num-cars {model_config[model_size]["num_cars"]}')
    nl.command(f'set num-garages {model_config[model_size]["num_garages"]}')

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

    nl.kill_workspace()
    metrics_df = pd.DataFrame(scores, columns=['rewards'])
    label_episodes(outpath, metrics_df, 'standard')


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument('-n', '--episodes', type=int, help='Number of episodes')
    parser.add_argument('-m', '--model_size', type=str, default='evaluation', choices=['training', 'evaluation'],
                        help='Control which model size to size')

    args = parser.parse_args()
    print(f" Baseline called with arguments: {vars(args)}")

    run_baseline(num_episodes=args.episodes, model_size=args.model_size)
