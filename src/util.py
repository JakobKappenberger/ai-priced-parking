import csv
import json
import os
import re
from glob import glob
from pathlib import Path
from typing import List, Dict

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from cmcrameri import cm

sns.set_style('dark')
sns.set_context('paper')

X_LABEL = [f"{int(x)}:00 AM" if x < 12 else f"{int(x - [12 if x != 12 else 0])}:00 PM" for x in np.arange(8, 22, 2)]


def add_bool_arg(parser, name, default=False):
    """
    Adds boolean arguments to parser by registering both the positive argument and the "no"-argument.
    :param parser:
    :param name: Name of argument.
    :param default:
    :return:
    """
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument('--' + name, dest=name, action='store_true')
    group.add_argument('--no-' + name, dest=name, action='store_false')
    parser.set_defaults(**{name: default})


def occupancy_reward_function(colours: List[str], current_state: Dict[str, float], global_mode=False):
    """
    Rewards occupancy rates between 75% and 90%. Punishes deviations exponentially.
    :param current_state: State dictionary.
    :param colours: Colours of different CPZs.
    :param global_mode: Whether or not to use the global occupancies or the one of the individual CPZs.
    :return: reward
    """
    reward = 0
    if global_mode:
        cpz_occupancies = [current_state['overall_occupancy']]
    else:
        cpz_occupancies = [current_state[f'{c}-lot occupancy'] for c in colours]

    for val in cpz_occupancies:
        if 0.75 < val < 0.9:
            reward += 1
        elif val <= 0.75:
            value = (1 - (abs(val - 0.825) / 0.825) ** -1.2)
            min_value = (1 - (abs(0 - 0.825) / 0.825) ** -1.2)
            max_value = (1 - (abs(0.75 - 0.825) / 0.825) ** -1.2)
            max_distance = max_value - min_value
            actual_distance = value - min_value
            reward += actual_distance / max_distance
        elif val >= 0.9:
            value = (1 - (abs(val - 0.825) / 0.825) ** -1.2)
            min_value = (1 - (abs(1 - 0.825) / 0.825) ** -1.2)
            max_value = (1 - (abs(0.9 - 0.825) / 0.825) ** -1.2)
            max_distance = max_value - min_value
            actual_distance = value - min_value
            reward += actual_distance / max_distance
    return reward / len(cpz_occupancies)


def n_cars_reward_function(colours: List[str], current_state: Dict[str, float]):
    """
    Minimizes the number of cars in the simulation.
    :param colours: Colours of different CPZs (only present to be able to use one call in custom_environment.py).
    :param current_state:State dictionary.
    :return: reward
    """
    return optimize_attr(current_state, "n_cars", mode="min")


def social_reward_function(colours: List[str], current_state: Dict[str, float]):
    """
    Maximizes the normalized share of poor cars in the model.
    :param colours: Colours of different CPZs (only present to be able to use one call in custom_environment.py).
    :param current_state:State dictionary.
    :return: reward
    """
    return optimize_attr(current_state, "normalized_share_poor")


def speed_reward_function(colours: List[str], current_state: Dict[str, float]):
    """
    Maximizes the average speed of the turtles in the model.
    :param colours: Colours of different CPZs (only present to be able to use one call in custom_environment.py).
    :param current_state:State dictionary.
    :return: reward
    """
    return optimize_attr(current_state, "mean_speed")


def composite_reward_function(colours: List[str], current_state: Dict[str, float]):
    """
    Maximizes 1/2 occupancy_reward_function + 1/4 n_cars_reward_function + 1/4 social_reward_function
    :param colours: Colours of different CPZs (only present to be able to use one call in custom_environment.py).
    :param current_state:State dictionary.
    :return: reward
    """
    return 0.5 * occupancy_reward_function(colours, current_state, global_mode=True) + 0.25 * n_cars_reward_function(
        colours, current_state) + 0.25 * social_reward_function(colours, current_state)


def optimize_attr(current_state: Dict[str, float], attr: str, mode="max"):
    """
    Abstract function to optimize attributes.
    :param mode: either "min" or "max" (default).
    :param current_state: State dictionary.
    :param attr: Attribute in state dictionary to optimize.
    :return: reward-value
    """
    if mode == "min":
        return abs(current_state[attr] - 1) ** 2
    else:
        return current_state[attr] ** 2


def document_episode(nl, path: Path, reward_sum):
    """
       Create directory for current episode and command NetLogo to save model as csv.
       :param nl: NetLogo-Session of environment.
       :param path: Path of current episode.
       :param reward_sum: Sum of accumulated rewards for episode.
       :return:
       """
    path.mkdir(parents=True, exist_ok=True)
    # Get all directories to check which episode this is
    dirs = glob(str(path) + "/E*.csv")
    current_episode = 1
    if dirs:
        last_episode = max(
            [int(re.findall("E(\d+)", dirs[i])[0]) for i in range(len(dirs))]
        )
        current_episode = last_episode + 1
    episode_path = str(path / f"E{current_episode}_{np.around(reward_sum, 8)}").replace("\\", "/")

    nl.command(f'export-world "{episode_path}.csv"')
    nl.command(f'export-view "{episode_path}.png"')


def label_episodes(path: Path, df: pd.DataFrame, mode: str):
    """
    Identifies worst, median and best episode of run. Renames them and saves plots.
    :param path: Path of current Experiment.
    :param df: DataFrame containing the results.
    :param mode: Usually either "training" or "evaluation".
    :return:
    """
    episode_files = glob(str(path) + "/E*.csv")
    performances = dict()
    performances['max'] = np.around(df.rewards.max(), 8)
    performances['min'] = np.around(df.rewards.min(), 8)
    performances['median'] = np.around(df.rewards.sort_values(ignore_index=True)[np.ceil(len(df) / 2) - 1], 8)

    print(f"Performances for {mode}:")
    print(performances)

    for metric in performances.keys():
        found = False
        for episode in episode_files:
            # Baseline
            if mode not in ["training", "eval"]:
                if str(performances[metric]) == episode.split('_')[1].split('.csv')[0]:
                    found = True
            elif str(performances[metric]) in episode:
                found = True
            if found:
                new_path = path / mode / metric
                new_path.mkdir(parents=True, exist_ok=True)
                save_plots(new_path, episode)
                os.rename(episode, str(new_path / f"{mode}_{metric}_{performances[metric]}.csv"))
                os.rename(episode.replace("csv", "png"),
                          str(new_path / f"view_{mode}_{metric}_{performances[metric]}.png"))
                episode_files.remove(episode)
                break


def delete_unused_episodes(path: Path):
    """
    Deletes episodes that did not produce either min, median or max performances to save storage.
    :param path: Path of current Experiment
    :return:
    """
    # Get all episodes not moved due to being min, median or max
    episode_files = glob(str(path) + "/E*")

    # Remove files of episodes
    for file in episode_files:
        if os.path.exists(file):
            os.remove(file)

    print("Unused Files deleted!")


def save_plots(outpath: Path, episode_path: str):
    """
    Calls all plot functions for given episode.
    :param outpath: Path to save plots.
    :param episode_path: Path of current episode.
    :return:
    """
    data_df = get_data_from_run(episode_path)
    for func in [
        plot_fees, plot_occup, plot_social, plot_n_cars, plot_speed, plot_income_stats, plot_share_yellow,
        plot_share_parked, plot_share_vanished
    ]:
        func(data_df, outpath)


def get_data_from_run(episode_path):
    """
    Extracts data for plots from episode.csv saved by NetLogo.
    :param episode_path: Path of current episode.
    :return: DataFrame with data of current episode.
    """
    # Open JSON file containing the indexing information required to extract the information needed for plotting
    with open('df_index.json', 'r') as fp:
        INDEX_DICT = json.load(fp=fp)

    with open(episode_path, newline='') as csvfile:
        file_reader = csv.reader(csvfile, delimiter=',', quotechar='"')
        for i, row in enumerate(file_reader):
            for key in INDEX_DICT.keys():
                if INDEX_DICT[key]['title'] in row:
                    INDEX_DICT[key]['i'] = i

    data_df = pd.read_csv(episode_path, skiprows=INDEX_DICT['fee']['i'] + 11, nrows=21601)
    data_df = data_df.rename(
        columns={"y": "yellow_lot_fee", "y.1": "teal_lot_fee", "y.2": "green_lot_fee", "y.3": "blue_lot_fee"})
    data_df = data_df[['x', 'yellow_lot_fee', 'green_lot_fee', 'teal_lot_fee', 'blue_lot_fee']]
    data_df.x = data_df.x / 1800
    del INDEX_DICT['fee']

    i = 0
    # Catch exceptions for different versions of NetLogo model run
    while i < len(INDEX_DICT.keys()):
        key = sorted(INDEX_DICT)[i]
        try:
            temp_df = pd.read_csv(episode_path, skiprows=INDEX_DICT[key]['i'] + INDEX_DICT[key]['offset'], nrows=21601)
            for j, col in enumerate(INDEX_DICT[key]['cols']):
                temp_df = temp_df.rename(columns={f"y.{j}" if j > 0 else "y": col})
            temp_df = temp_df[INDEX_DICT[key]['cols']]
            data_df = data_df.join(temp_df)
            i += 1
        except KeyError:
            INDEX_DICT[key]['offset'] += 1

    return data_df


def plot_fees(data_df, outpath):
    """
    Plot fees for CPZs over run of episode.
    :param data_df: DataFrame with data from current episode.
    :param outpath: Path to save plot.
    :return:
    """
    color_list = [cm.imola_r(0), cm.imola_r(1.0 * 1 / 3), cm.imola_r(1.0 * 2 / 3), cm.imola_r(1.0)]
    fig, ax = plt.subplots(1, 1, figsize=(20, 8), dpi=300)
    ax.plot(data_df.x, data_df.yellow_lot_fee, linewidth=4, color=color_list[0], linestyle='solid')
    ax.plot(data_df.x, data_df.green_lot_fee, linewidth=4, color=color_list[1], linestyle='dashed')
    ax.plot(data_df.x, data_df.teal_lot_fee, linewidth=4, color=color_list[2], linestyle='dashed')
    ax.plot(data_df.x, data_df.blue_lot_fee, linewidth=4, color=color_list[3], linestyle='dashed')

    ax.set_ylim(bottom=0, top=10.1)

    ax.set_ylabel('Hourly Fee in €', fontsize=30)
    ax.set_xlabel('', fontsize=30)
    ax.grid(True)
    ax.tick_params(axis='both', labelsize=25)
    ax.set_xlabel('Time of Day', fontsize=30)
    ax.set_xticks(ticks=np.arange(0, max(data_df["x"]) + 1, 2))
    ax.set_xticklabels(labels=X_LABEL)

    create_colourbar(fig)
    fig.savefig(str(outpath / 'fees.pdf'), bbox_inches='tight')
    plt.close(fig)


def plot_occup(data_df, outpath):
    """
    Plot occupation levels of different CPZs over run of episode.
    :param data_df: DataFrame with data from current episode.
    :param outpath: Path to save plot.
    :return:
    """
    # Save plot with three variants of legend location
    for loc in ["lower right", "right", "upper right"]:
        fig, ax = plt.subplots(1, 1, figsize=(20, 8), dpi=300)

        color_list = [cm.imola_r(0), cm.imola_r(1.0 * 1 / 3), cm.imola_r(1.0 * 2 / 3), cm.imola_r(1.0)]
        ax.plot(data_df.x, data_df.yellow_lot_occup / 100, linewidth=2, color=color_list[0])
        ax.plot(data_df.x, data_df.green_lot_occup / 100, linewidth=2, color=color_list[1])
        ax.plot(data_df.x, data_df.teal_lot_occup / 100, linewidth=2, color=color_list[2])
        ax.plot(data_df.x, data_df.blue_lot_occup / 100, linewidth=2, color=color_list[3])
        ax.plot(data_df.x, data_df.garages_occup / 100, label="Garage(s)", linewidth=2, color="black")
        ax.plot(data_df.x, data_df.overall_occup / 100, label="Kerbside Parking Overall", linewidth=4,
                color=cm.berlin(1.0), linestyle=(0, (1, 5))) if 'composite' in str(outpath).lower() else None
        ax.plot(data_df.x, [0.75] * len(data_df.x), linewidth=2, color="red", linestyle='dashed')
        ax.plot(data_df.x, [0.90] * len(data_df.x), linewidth=2, color="red", linestyle='dashed')
        ax.set_ylim(bottom=0, top=1.01)

        ax.set_ylabel('Utilised Capacity', fontsize=30)
        ax.grid(True)
        ax.tick_params(axis='both', labelsize=25)
        ax.set_xlabel('Time of Day', fontsize=30)
        ax.set_xticks(ticks=np.arange(0, max(data_df["x"]) + 1, 2))
        ax.set_xticklabels(labels=X_LABEL)
        create_colourbar(fig)
        ax.legend(fontsize=25, loc=loc)

        fig.savefig(str(outpath / f'occupancy_{loc}.pdf'), bbox_inches='tight')
        plt.close(fig)


def plot_social(data_df, outpath):
    """
    PLot shares of different income classes over run of episode.
    :param data_df: DataFrame with data from current episode.
    :param outpath: Path to save plot.
    :return:
    """
    # Save plot with three variants of legend location
    for loc in ["lower right", "right", "upper right"]:
        fig, ax = plt.subplots(1, 1, figsize=(20, 8), dpi=300)
        color_list = [cm.bamako(0), cm.bamako(1.0 * 1 / 2), cm.bamako(1.0)]
        ax.plot(data_df.x, data_df.low_income / 100, label="Low Income", linewidth=3, color=color_list[0])
        ax.plot(data_df.x, data_df.middle_income / 100, label="Middle Income", linewidth=3, color=color_list[1])
        ax.plot(data_df.x, data_df.high_income / 100, label="High Income", linewidth=3, color=color_list[2])
        ax.set_ylim(bottom=0, top=1.01)

        ax.set_ylabel('Share of Cars per Income Class', fontsize=30)
        ax.grid(True)
        ax.tick_params(axis='both', labelsize=25)
        ax.set_xlabel('Time of Day', fontsize=30)
        ax.set_xticks(ticks=np.arange(0, max(data_df["x"]) + 1, 2))
        ax.set_xticklabels(labels=X_LABEL)
        ax.legend(fontsize=25, loc=loc)

        fig.savefig(str(outpath / f'social_{loc}.pdf'), bbox_inches='tight')
        plt.close(fig)


def plot_speed(data_df, outpath):
    """
    Plot average speed over run of episode.
    :param data_df: DataFrame with data from current episode.
    :param outpath: Path to save plot.
    :return:
    """
    fig, ax = plt.subplots(1, 1, figsize=(20, 8), dpi=300)
    ax.plot(data_df.x, data_df.average_speed, linewidth=3, color=cm.bamako(0))
    ax.plot(data_df.x, data_df.average_speed.rolling(50).mean(), linewidth=3, color=cm.bamako(1.0))

    ax.set_ylim(bottom=0, top=1.01)

    ax.set_ylabel('Average Normalised Speed', fontsize=30)
    ax.grid(True)
    ax.tick_params(axis='both', labelsize=25)
    ax.set_xlabel('Time of Day', fontsize=30)
    ax.set_xticks(ticks=np.arange(0, max(data_df["x"]) + 1, 2))
    ax.set_xticklabels(labels=X_LABEL)

    fig.savefig(str(outpath / 'speed.pdf'), bbox_inches='tight')
    plt.close(fig)


def plot_n_cars(data_df, outpath):
    """
    Plot number of cars over run of episode.
    :param data_df: DataFrame with data from current episode.
    :param outpath: Path to save plot.
    :return:
    """
    fig, ax = plt.subplots(1, 1, figsize=(20, 8), dpi=300)
    ax.plot(data_df.x, data_df.cars_overall / 100, linewidth=3, color=cm.bamako(0))
    ax.set_ylim(bottom=0, top=1.01)

    ax.set_ylabel('Share of Initially Spawned Cars', fontsize=30)
    ax.grid(True)
    ax.tick_params(axis='both', labelsize=25)
    ax.set_xlabel('Time of Day', fontsize=30)
    ax.set_xticks(ticks=np.arange(0, max(data_df["x"]) + 1, 2))
    ax.set_xticklabels(labels=X_LABEL)

    fig.savefig(str(outpath / 'n_cars.pdf'), bbox_inches='tight')
    plt.close(fig)


def plot_income_stats(data_df, outpath):
    """
    Plot mean, median and std. of income distribution of run of episode.
    :param data_df: DataFrame with data from current episode.
    :param outpath: Path to save plot.
    :return:
    """
    # Save plot with three variants of legend location
    for loc in ["lower right", "right", "upper right"]:
        fig, ax = plt.subplots(1, 1, figsize=(20, 8), dpi=300)
        color_list = [cm.berlin(0), cm.berlin(1.0 * 1 / 2), cm.berlin(1.0)]
        ax.plot(data_df.x, data_df['mean'], label="Mean", linewidth=3, color=color_list[0])
        ax.plot(data_df.x, data_df['median'], label="Median", linewidth=3, color=color_list[1])
        ax.plot(data_df.x, data_df['std'], label="Standard Deviation", linewidth=3, color=color_list[2])
        ax.set_ylim(bottom=0, top=max(data_df[['mean', 'median', 'std']].max()) + 1)

        ax.set_ylabel('Income in €', fontsize=30)
        ax.grid(True)
        ax.tick_params(axis='both', labelsize=25)
        ax.set_xlabel('Time of Day', fontsize=30)
        ax.set_xticks(ticks=np.arange(0, max(data_df["x"]) + 1, 2))
        ax.set_xticklabels(labels=X_LABEL)
        ax.legend(fontsize=25, loc=loc)

        fig.savefig(str(outpath / f'income_stats_{loc}.pdf'), bbox_inches='tight')
        plt.close(fig)


def plot_share_yellow(data_df, outpath):
    """
    Plot share of different income classes on yellow CPZ.
    :param data_df: DataFrame with data from current episode.
    :param outpath: Path to save plot.
    :return:
    """
    # Save plot with three variants of legend location
    for loc in ["lower right", "right", "upper right"]:
        fig, ax = plt.subplots(1, 1, figsize=(20, 8), dpi=300)
        color_list = [cm.bamako(0), cm.bamako(1.0 * 1 / 2), cm.bamako(1.0)]
        ax.plot(data_df.x, data_df.share_y_low / 100, label="Low Income", linewidth=3, color=color_list[0])
        ax.plot(data_df.x, data_df.share_y_middle / 100, label="Middle Income", linewidth=3, color=color_list[1])
        ax.plot(data_df.x, data_df.share_y_high / 100, label="High Income", linewidth=3, color=color_list[2])
        ax.set_ylim(bottom=0, top=1.01)

        ax.set_ylabel('Share of Cars in Yellow CPZ', fontsize=30)
        ax.grid(True)
        ax.tick_params(axis='both', labelsize=25)
        ax.set_xlabel('Time of Day', fontsize=30)
        ax.set_xticks(ticks=np.arange(0, max(data_df["x"]) + 1, 2))
        ax.set_xticklabels(labels=X_LABEL)
        ax.legend(fontsize=25, loc=loc)

        fig.savefig(str(outpath / f'share_yellow_{loc}.pdf'), bbox_inches='tight')
        plt.close(fig)


def plot_share_parked(data_df, outpath):
    """
    Plot share of parked cars per income class.
    :param data_df: DataFrame with data from current episode.
    :param outpath: Path to save plot.
    :return:
    """
    # Save plot with three variants of legend location
    for loc in ["lower right", "right", "upper right"]:
        fig, ax = plt.subplots(1, 1, figsize=(20, 8), dpi=300)
        color_list = [cm.bamako(0), cm.bamako(1.0 * 1 / 2), cm.bamako(1.0)]
        ax.plot(data_df.x, data_df.share_p_low / 100, label="Low Income", linewidth=3, color=color_list[0])
        ax.plot(data_df.x, data_df.share_p_middle / 100, label="Middle Income", linewidth=3, color=color_list[1])
        ax.plot(data_df.x, data_df.share_p_high / 100, label="High Income", linewidth=3, color=color_list[2])
        ax.set_ylim(bottom=0, top=1.01)

        ax.set_ylabel('Share of Cars Finding Parking', fontsize=30)
        ax.grid(True)
        ax.tick_params(axis='both', labelsize=25)
        ax.set_xlabel('Time of Day', fontsize=30)
        ax.set_xticks(ticks=np.arange(0, max(data_df["x"]) + 1, 2))
        ax.set_xticklabels(labels=X_LABEL)
        ax.legend(fontsize=25, loc=loc)

        fig.savefig(str(outpath / f'share_parked_{loc}.pdf'), bbox_inches='tight')
        plt.close(fig)


def plot_share_vanished(data_df, outpath):
    """
    Plot share of vanished cars per income class.
    :param data_df: DataFrame with data from current episode.
    :param outpath: Path to save plot.
    :return:
    """
    # Save plot with three variants of legend location
    for loc in ["lower right", "right", "upper right"]:
        fig, ax = plt.subplots(1, 1, figsize=(20, 8), dpi=300)
        color_list = [cm.bamako(0), cm.bamako(1.0 * 1 / 2), cm.bamako(1.0)]
        ax.plot(data_df.x, data_df.share_v_low / (data_df.low_income[0] / 100 * 525), label="Low Income",
                linewidth=3,
                color=color_list[0])
        ax.plot(data_df.x, data_df.share_v_middle / (data_df.middle_income[0] / 100 * 525),
                label="Middle Income",
                linewidth=3, color=color_list[1])
        ax.plot(data_df.x, data_df.share_v_high / (data_df.high_income[0] / 100 * 525), label="High Income",
                linewidth=3, color=color_list[2])
        ax.set_ylim(bottom=0, top=1.01)

        ax.set_ylabel('Normalised Share of Cars Vanished', fontsize=30)
        ax.grid(True)
        ax.tick_params(axis='both', labelsize=25)
        ax.set_xlabel('Time of Day', fontsize=30)
        ax.set_xticks(ticks=np.arange(0, max(data_df["x"]) + 1, 2))
        ax.set_xticklabels(labels=X_LABEL)
        ax.legend(fontsize=25, loc=loc)

        fig.savefig(str(outpath / f'share_vanished_{loc}.pdf'), bbox_inches='tight')
        plt.close(fig)


def create_colourbar(fig):
    """
    Draws colourbar with colour of different CPZs on given figure.
    :param fig: Figure to draw colourbar on.
    :return:
    """
    cmap = cm.imola

    fig.subplots_adjust(bottom=0.1, top=0.9, left=0.1, right=0.8,
                        wspace=0.01)
    cb_ax = fig.add_axes([0.8, 0.1, 0.015, 0.8])

    bounds = [0, 1, 2, 3, 4]
    norm = matplotlib.colors.BoundaryNorm(bounds, cmap.N)
    cbar = fig.colorbar(matplotlib.cm.ScalarMappable(norm=norm, cmap=cmap),
                        cax=cb_ax, orientation='vertical')

    cbar.set_ticks([])
    cbar.ax.set_ylabel(r"$\Leftarrow$ Distance of CPZ to City Centre", fontsize=25, loc="top")
