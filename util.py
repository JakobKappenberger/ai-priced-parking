#from environment import CustomEnvironment


def occupancy_reward_function(env):
    """
    Rewards occupancy rates between 75% and 90%. Punishes deviations slightly.
    :param env: Environment-object
    :return:
    """
    reward = 0
    for c in env.colours:
        if 75 < env.current_state[f'{c}-lot occupancy'] < 90:
            reward += 5
        else:
            reward += -1

    return reward
