import json
import platform
import os
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path
from glob import glob

import wandb
import pandas as pd
import numpy as np
import pyNetLogo
from tqdm import tqdm, trange
from sklearn.model_selection import ParameterSampler

from util import add_bool_arg, document_episode, delete_unused_episodes, get_data_from_run

COLOURS = ['yellow', 'green', 'teal', 'blue']


def run_robustness_check(num_episodes: int, n_params: int, param_grid: list, nl_path: str = None, gui: bool = False, ):
    """
    Runs baseline experiments and save results.
    :param num_episodes: Number of episodes to run.
    :param nl_path: Path to NetLogo Installation (for Linux users)
    :param gui: Whether or not NetLogo UI is shown during episodes.
    :return:


    """
    # Connect to NetLogo
    if platform.system() == 'Linux':
        nl = pyNetLogo.NetLogoLink(gui=gui, netlogo_home=nl_path, netlogo_version="6.2")
    else:
        nl = pyNetLogo.NetLogoLink(gui=gui)
    nl.load_model('Model.nlogo')
    # Load model parameters
    with open('model_config.json', 'r') as fp:
        model_config = json.load(fp=fp)

    print(f"Configuring model size for evaluation")
    max_x_cor = model_config["evaluation"]['max_x_cor']
    max_y_cor = model_config["evaluation"]['max_y_cor']
    nl.command(f'resize-world {-max_x_cor} {max_x_cor} {-max_y_cor} {max_y_cor}')

    param_list = list(ParameterSampler(param_grid, n_iter=n_params))
    print(param_list)
    for config in tqdm(param_list, desc="Parameter Settings"):
        timestamp = datetime.now().strftime('%y%m-%d-%H%M')
        outpath = Path(".").absolute().parent / f"Experiments/robustness_check" / timestamp

        run = wandb.init(project="model_robustness", entity="jfrang", config=config, reinit=True)
        nl.command(f'set num-cars {wandb.config.num_cars}')
        nl.command(f'set parking-cars-percentage {run.config.parking_cars_percentage}')
        nl.command(f'set lot-distribution-percentage {run.config.lot_distribution_percentage}')
        nl.command(f'set target-start-occupancy {run.config.target_start_occupancy}')
        nl.command(f'set num-garages {run.config.num_garages}')
        nl.command('set dynamic-pricing-baseline false')

        scores = [0] * num_episodes
        traffic_counter = []
        share_cruising_counter = []

        for i in trange(num_episodes):
            episode_cruising = []
            nl.command('setup')

            # nl.command('set target-start-occupancy 0.5')
            # Disable rendering of view
            if not gui:
                nl.command('no-display')
            nl.command("ask one-of cars [record-data]")
            for _ in range(24):
                nl.repeat_command("go", 900)
                episode_cruising.append(nl.report("share-cruising"))
                for c in COLOURS:
                    occup = nl.report(f"{c}-lot-current-occup")
                    if 0.75 < occup < 0.9:
                        scores[i] += 0.25
            document_episode(nl=nl, path=outpath, reward_sum=scores[i])
            traffic_counter.append(nl.report("traffic-counter"))
            share_cruising_counter.append(np.mean(episode_cruising))

        metrics_df = pd.DataFrame(scores, columns=['rewards'])
        df = get_median_performance(outpath, metrics_df, 'standard')
        occup_score = 0
        for c in ['yellow', 'green', 'teal', 'blue']:
            occup_score += (len(df[(df[f'{c}_lot_occup'] > 75) & (df[f'{c}_lot_occup'] < 90)]) / len(df)) * 0.25
        n_cars_score = 1 - df['cars_overall'].iloc[-1] / 100
        speed_score = df.average_speed.mean()
        social_score = df.low_income.iloc[-1] / 100
        run.log({
            "Occupancy": occup_score,
            "Cars": n_cars_score,
            "Speed": speed_score,
            "Social": social_score,
            "Traffic Count": np.mean(traffic_counter),
            "Share Cruising": np.mean(share_cruising_counter)

        })
        delete_unused_episodes(outpath)
    nl.kill_workspace()


def get_median_performance(path: Path, df: pd.DataFrame, mode: str):
    """
    Identifies worst, median and best episode of run. Renames them and saves plots.
    :param path: Path of current Experiment.
    :param df: DataFrame containing the results.
    :param mode: Usually either "training" or "evaluation".
    :return:
    """
    episode_files = glob(str(path) + "/E*.csv")
    print(episode_files)
    median_performance = np.around(df.rewards.sort_values(ignore_index=True)[np.ceil(len(df) / 2) - 1], 8)

    print(f"Median performances for {mode}:")
    print(median_performance)

    if median_performance == 0.0:
        median_performance = 0
    found = False
    for episode in episode_files:
        print(episode.split('_')[-1].split('.csv')[0])
        # Baseline
        if mode not in ["training", "eval"]:
            if str(median_performance) == episode.split('_')[-1].split('.csv')[0]:
                found = True
        elif str(median_performance) in episode:
            found = True
        if found:
            new_path = path / mode / "median"
            new_path.mkdir(parents=True, exist_ok=True)
            print(episode)
            data_df = get_data_from_run(episode)

            os.rename(episode, str(new_path / f"{mode}_median_{median_performance}.csv"))
            os.rename(episode.replace("csv", "png"),
                      str(new_path / f"view_{mode}_median_{median_performance}.png"))
            episode_files.remove(episode)
            return data_df


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument('episodes', type=int, help='Number of episodes')
    parser.add_argument('n_params', type=int, help='Number of Parameter Settings to try')
    parser.add_argument('-np', '--nl_path', type=str, default=None,
                        help='Path to NetLogo directory (for Linux Users)')
    add_bool_arg(parser, 'gui', default=False)

    args = parser.parse_args()
    print(f" Robustness Check called with arguments: {vars(args)}")

    param_grid = ({
        "num_cars": list(range(300, 600, 25)),
        "lot_distribution_percentage": list(np.round(np.linspace(0.3, 1, 8), 2)),
        "target_start_occupancy": list(np.round(np.linspace(0.3, 1, 8), 2)),
        "parking_cars_percentage": list(range(30, 100, 10)),
        "num_garages": list(range(1, 4, 1))
    })

    run_robustness_check(num_episodes=args.episodes, n_params=args.n_params, param_grid=param_grid,
                         nl_path=args.nl_path, gui=args.gui)
