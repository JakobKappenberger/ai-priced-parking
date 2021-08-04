import csv
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

INDEX_DICT = {
    'capacity': {
        'title': '"Utilized Capacity at Different Lots"'
    },
    'fee': {
        'title': '"Dynamic Fee of Different Lots"'
    },
    'cars': {
        'title': '"Share of Cars per Income Class"'
    },
    'speed': {
        'title': '"Average Wait Time of Cars"'
    },
    'income': {
        'title': '"Descriptive Income Statistics"'
    },
    'share_yellow': {
        'title': '"Share of Income Class on Yellow Lot"'
    },
    'vanished_cars': {
        'title': '"Vanished Vars per Income Class"'
    }
}


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
        if val <= 0.825:
            reward += 1 - (abs(val - 0.825) / 0.825) ** 0.4
        else:
            value = 1 - (abs(val - 0.825) / 0.825) ** 0.4
            min_value = 1 - (abs(1 - 0.825) / 0.825) ** 0.4
            max_value = 1 - (abs(0.825 - 0.825) / 0.825) ** 0.4
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
    Maximizes the entropy of the income distribution in the model.
    :param colours: Colours of different CPZs (only present to be able to use one call in custom_environment.py).
    :param current_state:State dictionary.
    :return: reward
    """
    return optimize_attr(current_state, "income_entropy")


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
    # Get all directories to check, which episode this is
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
    Identifies worst, median and best episode of run. Renames them and saves plots for them.
    :param path: Path of current Experiment.
    :param df: DataFrame containing the results.
    :param mode: Usually either "training" or "evaluation".
    :return:
    """
    episode_files = glob(str(path) + "/E*.csv")
    performances = dict()
    performances['max'] = np.around(df.rewards.max(), 8)
    performances['min'] = np.around(df.rewards.min(), 8)
    performances['median'] = np.around(df.rewards.sort_values()[np.ceil(len(df) / 2)], 8)

    print(f"Performances for {mode}:")
    print(performances)

    for metric in performances.keys():
        found = False
        for episode in episode_files:
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
    episode_files = glob(str(path) + "/E*")

    # Remove files of other episodes
    for file in episode_files:
        if os.path.exists(file):
            os.remove(file)

    print("Unused Files deleted!")


def save_plots(outpath: Path, episode_path: str):
    """
    Calls all plot function for given episode.
    :param outpath: Path to save plots.
    :param episode_path: Path of current episode.
    :return:
    """
    data_df = get_data_from_run(episode_path)
    for func in [
        plot_fees, plot_occup, plot_social, plot_n_cars,
        plot_speed, plot_income_stats, plot_share_yellow, plot_share_vanished
    ]:
        func(data_df, outpath)


def get_data_from_run(episode_path):
    """
    Extracts data for plots from episode.csv saved by NetLogo.
    :param episode_path: Path of current episode.
    :return: DataFrame with data of current episode.
    """
    with open(episode_path, newline='') as csvfile:
        file_reader = csv.reader(csvfile, delimiter=',', quotechar='"')
        for i, row in enumerate(file_reader):
            for key in INDEX_DICT.keys():
                if INDEX_DICT[key]['title'] in row:
                    INDEX_DICT[key]['i'] = i

    fee_df = pd.read_csv(episode_path, skiprows=INDEX_DICT['fee']['i'] + 11, nrows=21601)
    fee_df = fee_df.rename(
        columns={"y": "yellow_lot_fee", "y.1": "teal_lot_fee", "y.2": "green_lot_fee", "y.3": "blue_lot_fee"})
    fee_df = fee_df[['x', 'yellow_lot_fee', 'green_lot_fee', 'teal_lot_fee', 'blue_lot_fee']]
    fee_df.x = fee_df.x / 1800

    occup_df = pd.read_csv(episode_path, skiprows=INDEX_DICT['capacity']['i'] + 14, nrows=21601)
    occup_df = occup_df.rename(
        columns={"y": "blue_lot_occup", "y.1": "yellow_lot_occup", "y.2": "green_lot_occup", "y.3": "teal_lot_occup",
                 "y.4": "garages_occup"})
    occup_df = occup_df[['yellow_lot_occup', 'green_lot_occup', 'teal_lot_occup', 'blue_lot_occup', 'garages_occup']]
    data_df = fee_df.join(occup_df)

    cars_df = pd.read_csv(episode_path, skiprows=INDEX_DICT['cars']['i'] + 12, nrows=21601)
    cars_df = cars_df.rename(
        columns={"y": "high_income", "y.1": "middle_income", "y.2": "low_income", "y.3": "cars_overall",
                 "y.4": "income_entropy"})
    cars_df = cars_df[['high_income', 'middle_income', 'low_income', 'cars_overall', 'income_entropy']]

    data_df = data_df.join(cars_df)

    speed_df = pd.read_csv(episode_path, skiprows=INDEX_DICT['speed']['i'] + 9, nrows=21601)
    speed_df = speed_df.rename(columns={"y": "average_wait_time", "y.1": "average_speed"})
    speed_df = speed_df[['average_wait_time', 'average_speed']]

    data_df = data_df.join(speed_df)

    income_df = pd.read_csv(episode_path, skiprows=INDEX_DICT['income']['i'] + 10, nrows=21601)
    income_df = income_df.rename(columns={"y": "mean", "y.1": "median", "y.2": "std"})
    income_df = income_df[['mean', 'median', 'std']]

    data_df = data_df.join(income_df)

    share_df = pd.read_csv(episode_path, skiprows=INDEX_DICT['share_yellow']['i'] + 10, nrows=21601)
    share_df = share_df.rename(columns={"y": "share_y_high", "y.1": "share_y_middle", "y.2": "share_y_low"})
    share_df = share_df[['share_y_high', 'share_y_middle', 'share_y_low']]

    data_df = data_df.join(share_df)

    vanished_df = pd.read_csv(episode_path, skiprows=INDEX_DICT['vanished_cars']['i'] + 10, nrows=21601)
    vanished_df = vanished_df.rename(columns={"y": "share_v_low", "y.1": "share_v_middle", "y.2": "share_v_high"})
    vanished_df = vanished_df[['share_v_high', 'share_v_middle', 'share_v_low']]

    data_df = data_df.join(vanished_df)

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
    ax.set_xticklabels(labels=[f"{int(x + 8)}:00" for x in np.arange(0, max(data_df["x"]) + 1, 2)])

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
        ax.plot(data_df.x, data_df.yellow_lot_occup, linewidth=2, color=color_list[0])
        ax.plot(data_df.x, data_df.green_lot_occup, linewidth=2, color=color_list[1])
        ax.plot(data_df.x, data_df.teal_lot_occup, linewidth=2, color=color_list[2])
        ax.plot(data_df.x, data_df.blue_lot_occup, linewidth=2, color=color_list[3])
        ax.plot(data_df.x, data_df.garages_occup, label="Garage(s)", linewidth=2, color="black")
        ax.plot(data_df.x, [75] * len(data_df.x), linewidth=2, color="red", linestyle='dashed')
        ax.plot(data_df.x, [90] * len(data_df.x), linewidth=2, color="red", linestyle='dashed')
        ax.set_ylim(bottom=0, top=101)

        ax.set_ylabel('Occupancy', fontsize=30)
        ax.grid(True)
        ax.tick_params(axis='both', labelsize=25)
        ax.set_xlabel('Time of Day', fontsize=30)
        ax.set_xticks(ticks=np.arange(0, max(data_df["x"]) + 1, 2))
        ax.set_xticklabels(labels=[f"{int(x + 8)}:00" for x in np.arange(0, max(data_df["x"]) + 1, 2)])
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
        ax.plot(data_df.x, data_df.low_income, label="Low Income", linewidth=3, color=color_list[0])
        ax.plot(data_df.x, data_df.middle_income, label="Middle Income", linewidth=3, color=color_list[1])
        ax.plot(data_df.x, data_df.high_income, label="High Income", linewidth=3, color=color_list[2])
        ax.set_ylim(bottom=0, top=101)

        ax.set_ylabel('Share of Cars per Income Class', fontsize=30)
        ax.grid(True)
        ax.tick_params(axis='both', labelsize=25)
        ax.set_xlabel('Time of Day', fontsize=30)
        ax.set_xticks(ticks=np.arange(0, max(data_df["x"]) + 1, 2))
        ax.set_xticklabels(labels=[f"{int(x + 8)}:00" for x in np.arange(0, max(data_df["x"]) + 1, 2)])
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

    ax.set_ylabel('Average Normalized Speed', fontsize=30)
    ax.grid(True)
    ax.tick_params(axis='both', labelsize=25)
    ax.set_xlabel('Time of Day', fontsize=30)
    ax.set_xticks(ticks=np.arange(0, max(data_df["x"]) + 1, 2))
    ax.set_xticklabels(labels=[f"{int(x + 8)}:00" for x in np.arange(0, max(data_df["x"]) + 1, 2)])

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
    ax.plot(data_df.x, data_df.cars_overall, linewidth=3, color=cm.bamako(0))
    ax.set_ylim(bottom=0, top=101)

    ax.set_ylabel('Share of Initially Spawned Cars', fontsize=30)
    ax.grid(True)
    ax.tick_params(axis='both', labelsize=25)
    ax.set_xlabel('Time of Day', fontsize=30)
    ax.set_xticks(ticks=np.arange(0, max(data_df["x"]) + 1, 2))
    ax.set_xticklabels(labels=[f"{int(x + 8)}:00" for x in np.arange(0, max(data_df["x"]) + 1, 2)])

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
        ax.set_xticklabels(labels=[f"{int(x + 8)}:00" for x in np.arange(0, max(data_df["x"]) + 1, 2)])
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
        ax.plot(data_df.x, data_df.share_y_low, label="Low Income", linewidth=3, color=color_list[0])
        ax.plot(data_df.x, data_df.share_y_middle, label="Middle Income", linewidth=3, color=color_list[1])
        ax.plot(data_df.x, data_df.share_y_high, label="High Income", linewidth=3, color=color_list[2])
        ax.set_ylim(bottom=0, top=101)

        ax.set_ylabel('Share of Cars in Yellow CPZ', fontsize=30)
        ax.grid(True)
        ax.tick_params(axis='both', labelsize=25)
        ax.set_xlabel('Time of Day', fontsize=30)
        ax.set_xticks(ticks=np.arange(0, max(data_df["x"]) + 1, 2))
        ax.set_xticklabels(labels=[f"{int(x + 8)}:00" for x in np.arange(0, max(data_df["x"]) + 1, 2)])
        ax.legend(fontsize=25, loc=loc)

        fig.savefig(str(outpath / f'share_yellow_{loc}.pdf'), bbox_inches='tight')
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
        ax.plot(data_df.x, data_df.share_v_low, label="Low Income", linewidth=3, color=color_list[0])
        ax.plot(data_df.x, data_df.share_v_middle, label="Middle Income", linewidth=3, color=color_list[1])
        ax.plot(data_df.x, data_df.share_v_high, label="High Income", linewidth=3, color=color_list[2])
        ax.set_ylim(bottom=0)

        ax.set_ylabel('Vanished Cars', fontsize=30)
        ax.grid(True)
        ax.tick_params(axis='both', labelsize=25)
        ax.set_xlabel('Time of Day', fontsize=30)
        ax.set_xticks(ticks=np.arange(0, max(data_df["x"]) + 1, 2))
        ax.set_xticklabels(labels=[f"{int(x + 8)}:00" for x in np.arange(0, max(data_df["x"]) + 1, 2)])
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
