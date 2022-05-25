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
from robustness_check import get_median_performance


def train():
    # Connect to NetLogo
    nl = pyNetLogo.NetLogoLink()
    nl.load_model('Model.nlogo')
    # Load model parameters
    with open('model_config.json', 'r') as fp:
        model_config = json.load(fp=fp)

    print(f"Configuring model size for evaluation")
    max_x_cor = model_config["evaluation"]['max_x_cor']
    max_y_cor = model_config["evaluation"]['max_y_cor']
    nl.command(f'resize-world {-max_x_cor} {max_x_cor} {-max_y_cor} {max_y_cor}')

    wandb.init(magic=True)

    timestamp = datetime.now().strftime('%y%m-%d-%H%M')
    outpath = Path(".").absolute().parent / f"Experiments/robustness_check" / timestamp
    wandb.config['model_size'] = (max_x_cor, max_y_cor)
    nl.command(f'set num-cars {wandb.config.num_cars}')
    nl.command(f'set parking-cars-percentage {wandb.config.parking_cars_percentage * 100}')
    nl.command(f'set lot-distribution-percentage {wandb.config.lot_distribution_percentage}')
    nl.command(f'set target-start-occupancy {wandb.config.target_start_occupancy}')
    nl.command(f'set num-garages {wandb.config.num_garages}')
    nl.command('set dynamic-pricing-baseline false')

    scores = [0] * 3
    traffic_counter = []
    share_cruising_counter = []

    for i in trange(3):
        episode_cruising = []
        nl.command('setup')

        # nl.command('set target-start-occupancy 0.5')
        # Disable rendering of view
        nl.command('no-display')
        nl.command("ask one-of cars [record-data]")
        for _ in range(24):
            nl.repeat_command("go", 900)
            episode_cruising.append(nl.report("share-cruising"))
        traffic_counter.append(nl.report("traffic-counter"))
        scores[i] = traffic_counter[i]
        document_episode(nl=nl, path=outpath, reward_sum=scores[i])
        share_cruising_counter.append(np.mean(episode_cruising))

    metrics_df = pd.DataFrame(scores, columns=['rewards'])
    df = get_median_performance(outpath, metrics_df, 'standard')
    occup_score = 0
    for c in ['yellow', 'green', 'teal', 'blue']:
        occup_score += (len(df[(df[f'{c}_lot_occup'] > 75) & (df[f'{c}_lot_occup'] < 90)]) / len(df)) * 0.25
    n_cars_score = 1 - df['cars_overall'].iloc[-1] / 100
    speed_score = df.average_speed.mean()
    social_score = df.low_income.iloc[-1] / 100
    wandb.log({
        "Occupancy": occup_score,
        "Cars": n_cars_score,
        "Speed": speed_score,
        "Social": social_score,
        "Traffic Count": np.mean(traffic_counter),
        "Share Cruising": np.mean(share_cruising_counter),
        "target_function": (1 - (abs(np.mean(traffic_counter) - 5600) / 5600)) * 1000 + (
                    (1 - (abs(np.mean(share_cruising_counter) - 0.35) / 0.35)) * 1000)
    })
    delete_unused_episodes(outpath)

    nl.kill_workspace()


if __name__ == '__main__':
    train()
