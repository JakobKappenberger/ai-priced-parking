# from environment import CustomEnvironment
import csv
import re
from glob import glob
from pathlib import Path
from typing import List, Dict

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from cmcrameri import cm


def occupancy_reward_function(colours: List[str], current_state: Dict[str, float], global_mode=False):
    """
    Rewards occupancy rates between 75% and 90%. Punishes deviations as the squared deviation from the target range.
    :param current_state:
    :param colours:
    :param global_mode:
    :return:
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

    :param colours:
    :param current_state:
    :return:
    """
    return optimize_attr(current_state, "n_cars", mode="min")


def social_reward_function(colours: List[str], current_state: Dict[str, float]):
    """

    :param colours:
    :param current_state:
    :return:
    """
    return optimize_attr(current_state, "income_entropy")


def speed_reward_function(colours: List[str], current_state: Dict[str, float]):
    """

    :param colours:
    :param current_state:
    :return:
    """
    return optimize_attr(current_state, "mean_speed")


def composite_reward_function(colours: List[str], current_state: Dict[str, float]):
    """

    :param colours:
    :param current_state:
    :return:
    """
    return 0.5 * occupancy_reward_function(colours, current_state, global_mode=True) + 0.25 * n_cars_reward_function(
        colours, current_state) + 0.25 * social_reward_function(colours, current_state)


def optimize_attr(current_state: Dict[str, float], attr: str, mode="max"):
    """

    :param mode:
    :param current_state:
    :param attr:
    :return:
    """
    if mode == "min":
        return abs(current_state[attr] - 1) ** 2
    else:
        return current_state[attr] ** 2


def document_episode(nl, path: Path, reward_sum):
    """
       Create directory for current episode and command NetLogo to save model as csv
       :param reward_sum:
       :param nl: NetLogo-Session of environment
       :param path: Path of current environment
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


def save_plots(outpath: Path, episode_path: str):
    """

    :param outpath:
    :param episode_path:
    :return:
    """
    data_df = get_data_from_run(episode_path)
    for func in [plot_fees, plot_occup, plot_social, plot_n_cars, plot_speed]:
        func(data_df, outpath)


def get_data_from_run(episode_path):
    """

    :param episode_path:
    :return:
    """
    capacity_i = 0
    fee_i = 0
    cars_i = 0
    speed_i = 0
    with open(episode_path, newline='') as csvfile:
        file_reader = csv.reader(csvfile, delimiter=',', quotechar='"')
        for i, row in enumerate(file_reader):
            if '"Utilized Capacity at Different Lots"' in row:
                capacity_i = i
            elif '"Dynamic Fee of Different Lots"' in row:
                fee_i = i
            elif '"Share of Cars per Income Class"' in row:
                cars_i = i
            elif '"Average Wait Time of Cars"' in row:
                speed_i = i

    fee_df = pd.read_csv(episode_path, skiprows=fee_i + 11, nrows=21601)
    fee_df = fee_df.rename(
        columns={"y": "yellow_lot_fee", "y.1": "green_lot_fee", "y.2": "teal_lot_fee", "y.3": "blue_lot_fee"})
    fee_df = fee_df[['x', 'yellow_lot_fee', 'green_lot_fee', 'teal_lot_fee', 'blue_lot_fee']]
    fee_df.x = fee_df.x / 1800

    occup_df = pd.read_csv(episode_path, skiprows=capacity_i + 14, nrows=21601)
    occup_df = occup_df.rename(
        columns={"y": "blue_lot_occup", "y.1": "yellow_lot_occup", "y.2": "green_lot_occup", "y.3": "teal_lot_occup",
                 "y.4": "garages_occup"})
    occup_df = occup_df[['yellow_lot_occup', 'green_lot_occup', 'teal_lot_occup', 'blue_lot_occup', 'garages_occup']]
    data_df = fee_df.join(occup_df)

    cars_df = pd.read_csv(episode_path, skiprows=cars_i + 12, nrows=21601)
    cars_df = cars_df.rename(
        columns={"y": "high_income", "y.1": "middle_income", "y.2": "low_income", "y.3": "cars_overall",
                 "y.4": "income_entropy"})
    cars_df = cars_df[['high_income', 'middle_income', 'low_income', 'cars_overall', 'income_entropy']]

    data_df = data_df.join(cars_df)

    speed_df = pd.read_csv(episode_path, skiprows=speed_i + 9, nrows=21601)
    speed_df = speed_df.rename(columns={"y": "average_wait_time", "y.1": "average_speed"})
    speed_df = speed_df[['average_wait_time', 'average_speed']]

    data_df = data_df.join(speed_df)

    return data_df


def plot_fees(data_df, outpath, linestyle="solid"):
    """

    :param data_df:
    :param linestyle:
    :return:
    """
    color_list = [cm.imola_r(0), cm.imola_r(1.0 * 1 / 3), cm.imola_r(1.0 * 2 / 3), cm.imola_r(1.0)]
    fig, ax = plt.subplots(1, 1, figsize=(20, 8), dpi=300)
    ax.plot(data_df.x, data_df.yellow_lot_fee, linewidth=4, color=color_list[0], linestyle=linestyle)
    ax.plot(data_df.x, data_df.green_lot_fee, linewidth=4, color=color_list[1], linestyle=linestyle)
    ax.plot(data_df.x, data_df.teal_lot_fee, linewidth=4, color=color_list[2], linestyle=linestyle)
    ax.plot(data_df.x, data_df.blue_lot_fee, linewidth=4, color=color_list[3], linestyle=linestyle)

    ax.set_ylim(bottom=0, top=10.1)

    ax.set_ylabel('Hourly Fee in €', fontsize=30)
    ax.set_xlabel('', fontsize=30)
    ax.grid(True)
    ax.tick_params(axis='both', labelsize=25)
    ax.set_xlabel('Time of Day', fontsize=30)
    ax.set_xticks(ticks=np.arange(0, max(data_df["x"]) + 1, 2))
    ax.set_xticklabels(labels=[f"{int(x + 8)}:00" for x in np.arange(0, max(data_df["x"]) + 1, 2)])

    create_colourbar(fig)
    fig.savefig(str(outpath / 'fees.png'), bbox_inches='tight')
    plt.close(fig)


def plot_occup(data_df, outpath):
    """

    :param data_df:
    :return:
    """
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
    ax.legend(fontsize=25)

    fig.savefig(str(outpath / 'occupancy.png'), bbox_inches='tight')
    plt.close(fig)


def plot_social(data_df, outpath):
    """

    :param data_df:
    :return:
    """
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
    ax.legend(fontsize=25)

    fig.savefig(str(outpath / 'social.png'), bbox_inches='tight')
    plt.close(fig)


def plot_speed(data_df, outpath):
    """

    :param data_df:
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

    fig.savefig(str(outpath / 'speed.png'), bbox_inches='tight')
    plt.close(fig)


def plot_n_cars(data_df, outpath):
    """

    :param data_df:
    :return:
    """
    fig, ax = plt.subplots(1, 1, figsize=(20, 8), dpi=300)
    ax.plot(data_df.x, data_df.cars_overall, linewidth=3, color=cm.bamako(0))
    ax.set_ylim(bottom=0, top=101)

    ax.set_ylabel('Share of Originally Spawned Cars', fontsize=30)
    ax.grid(True)
    ax.tick_params(axis='both', labelsize=25)
    ax.set_xlabel('Time of Day', fontsize=30)
    ax.set_xticks(ticks=np.arange(0, max(data_df["x"]) + 1, 2))
    ax.set_xticklabels(labels=[f"{int(x + 8)}:00" for x in np.arange(0, max(data_df["x"]) + 1, 2)])

    fig.savefig(str(outpath / 'n_cars.png'), bbox_inches='tight')
    plt.close(fig)


def create_colourbar(fig):
    """
    """
    cmap = cm.imola

    fig.subplots_adjust(bottom=0.1, top=0.9, left=0.1, right=0.8,
                        wspace=0.02, hspace=0.1)
    cb_ax = fig.add_axes([0.83, 0.1, 0.02, 0.8])

    bounds = [0, 1, 2, 3, 4]
    norm = matplotlib.colors.BoundaryNorm(bounds, cmap.N)
    cbar = fig.colorbar(matplotlib.cm.ScalarMappable(norm=norm, cmap=cmap),
                        cax=cb_ax, orientation='vertical')

    cbar.set_ticks([])
    cbar.ax.set_ylabel(r"$\Leftarrow$ Distance to City Centre", fontsize=25, loc="top")
