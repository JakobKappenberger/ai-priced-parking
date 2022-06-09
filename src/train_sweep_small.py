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
from sklearn.metrics.pairwise import euclidean_distances

from util import (
    add_bool_arg,
    document_episode,
    delete_unused_episodes,
    get_data_from_run,
)
from robustness_check import get_median_performance

Z = [-5.58662028e-04, 2.76514862e-02, -4.09343614e-01, 2.31844786e00]
COLOURS = ["yellow", "green", "teal", "blue"]


def train():
    # Connect to NetLogo
    nl = pyNetLogo.NetLogoLink()
    nl.load_model("Model.nlogo")
    # Load model parameters
    with open("model_config.json", "r") as fp:
        model_config = json.load(fp=fp)

    print(f"Configuring model size for training")
    max_x_cor = model_config["training"]["max_x_cor"]
    max_y_cor = model_config["training"]["max_y_cor"]
    nl.command(f"resize-world {-max_x_cor} {max_x_cor} {-max_y_cor} {max_y_cor}")
    p = np.poly1d(Z)

    config_defaults = {
        "lot_distribution_percentage": model_config["training"][
            "lot_distribution_percentage"
        ],
        "target_start_occupancy": model_config["training"]["target_start_occupancy"],
        "num_garages": model_config["training"]["num_garages"],
        "model_size": (max_x_cor, max_y_cor),
        "parking_cars_percentage_increment": model_config["training"][
            "parking_cars_percentage_intercept"
        ],
    }

    print(config_defaults)
    wandb.init(config=config_defaults, magic=True)
    wandb.config.setdefaults(config_defaults)

    print(wandb.config)

    timestamp = datetime.now().strftime("%y%m-%d-%H%M")
    outpath = Path(".").absolute().parent / f"Experiments/robustness_check" / timestamp
    nl.command(f"set num-cars {wandb.config.num_cars}")
    nl.command(f"set target-start-occupancy {wandb.config.target_start_occupancy}")
    nl.command(f"set num-garages {wandb.config.num_garages}")
    nl.command(
        f"set lot-distribution-percentage {wandb.config.lot_distribution_percentage}"
    )
    nl.command("set dynamic-pricing-baseline false")

    scores = [0] * 5
    traffic_counter = []
    share_cruising_counter = []

    for i in trange(5):
        episode_cruising = []
        nl.command("setup")

        # nl.command('set target-start-occupancy 0.5')
        # Disable rendering of view
        nl.command("no-display")
        # Turn dynamic baseline pricing mechanism off
        nl.command("set dynamic-pricing-baseline false")
        for c in COLOURS:
            if c in ["yellow", "green"]:
                nl.command(f"change-fee-free {c}-lot 3.6")
            else:
                nl.command(f"change-fee-free {c}-lot 1.8")
        nl.command("ask one-of cars [record-data]")
        for j in range(24):
            nl.command(
                f"set parking-cars-percentage {(p(j / 2 + 8) + wandb.config.parking_cars_percentage_increment) * 100}"
            )
            nl.repeat_command("go", 900)
            episode_cruising.append(nl.report("share-cruising"))
        traffic_counter.append(nl.report("traffic-counter"))
        scores[i] = traffic_counter[i]
        document_episode(nl=nl, path=outpath, reward_sum=scores[i])
        share_cruising_counter.append(np.mean(episode_cruising))

    metrics_df = pd.DataFrame(scores, columns=["rewards"])
    df = get_median_performance(outpath, metrics_df, "standard")
    occup_score = 0
    for c in ["yellow", "green", "teal", "blue"]:
        occup_score += (
            len(df[(df[f"{c}_lot_occup"] > 75) & (df[f"{c}_lot_occup"] < 90)]) / len(df)
        ) * 0.25
    n_cars_score = 1 - df["cars_overall"].iloc[-1] / 100
    speed_score = df.average_speed.mean()
    social_score = df.low_income.iloc[-1] / 100
    eval_vec = np.array(
        [
            0.019966722129783676,
            0.0600087958890792,
            0.5635815586761667,
            0.22410865874363328,
            0.1665297264211474,
        ]
    ).reshape(1, -1)
    train_vec = np.array(
        [
            n_cars_score,
            occup_score,
            np.mean(share_cruising_counter),
            social_score,
            speed_score,
        ]
    ).reshape(1, -1)
    print(train_vec)
    wandb.log(
        {
            "Occupancy": occup_score,
            "Cars": n_cars_score,
            "Speed": speed_score,
            "Social": social_score,
            "Traffic Count": np.mean(traffic_counter),
            "Share Cruising": np.mean(share_cruising_counter),
            "target_function": euclidean_distances(eval_vec, train_vec) * 1000,
        }
    )
    delete_unused_episodes(outpath)
    print(euclidean_distances(eval_vec, train_vec))

    nl.kill_workspace()


if __name__ == "__main__":
    train()
