# Modelling Dynamic Pricing Schemes for Parking in Inner Cities: A Reinforcement Learning Approach

The repository at hand allows for the complete replication of all experiments conducted.

## Setup
*Before beginning, make sure to have 
 [NetLogo 6.2](https://ccl.northwestern.edu/netlogo/download.shtml) installed. On Windows, the installation should be detected automatically. Linux users must specify the respective path.*
```
# Build Environment
cd project_folder
conda env create -f environment.yml
# Activate Environment
conda activate thesis_gutmann
```

## Using this Repository
There are three main functionalities included in this repository:

**1. Execute the baseline:**

```
# To run baseline for 50 episodes
cd project_folder/src
python run_baseline.py 50
```

- **episodes** (required): Number of episodes to run the baseline for
- **--[m]odel_size**: Size of the NetLogo Grid zu use (either "training" or "evaluation"(default))
- **--[n]etlogo_[p]ath**: Path to NetLogo installation (for Linux users only)
- **--gui**: Boolean for NetLogo UI (default false)

**2. Conduct Reinforcement Learning experiments:**
```
# Train locally for 1.000 episodes on four cores
cd project_folder/src
python run_experiments.py ppo_agent_local.json 1000 -p 4
# Evaluate the policies learnt during training
python run_experiments.py ppo_agent_local.json 50 -c 2108-10-0826 --eval --zip
```

- **episodes** (required): Number of episodes to train for
- **agent** (required): Path to agent JSON config file
- **--num_[p]arallel**: CPU cores to use, defaults to 1
- **--[r]eward_key**: Reward function to use, defaults to "occupancy"
- **--[c]heckpoint**: Checkpoint of previous training process, either used to resume training or for evaluation
- **--[m]odel_size**: Size of the NetLogo Grid zu use (either "training"(default) or "evaluation")
- **--[n]etlogo_[p]ath**: Path to NetLogo installation (for Linux users only)
- **--batch_agent_calls**: Run agent calls in batches, default to False
- **--sync_episodes**: Sync agent calls between parallel episodes, defaults to False
- **--document**: Save plots for min, median and max performances, defaults to True
- **--adjust_free**: Let agent adjust prices freely in interval between 0 and 10, defaults to True
- **--eval**: Run one model instance in evaluation mode, defaults to False
- **--zip**: Zip directory of run after experiment is finished, defaults to False
- **--gui**: Boolean for NetLogo UI (default false)

**3. Perform hyperparameter tuning for these experiments:**
```
# Tune hyperparameters for 5.400 episodes per iteration, on 36 cores, with two survivors per round
cd project_folder/src
python tune.py -e custom_environment.CustomEnvironment -m 24 -n 5400 -p 36 -rk occupancy -s 2 -r 1,1,1,2,3 -c tune_config.json
```
- **--episodes [n]** (required): Number of episodes to train per iteration
- **--[e]nvironment** (required): TensorForce-Environment (name, configuration JSON file, or library module)
- **--[m]ax_episode_timesteps** (required): Maximum time steps per episode
- **--num_[p]arallel**: CPU cores to use, defaults to 1
- **--[r]eward_[k]ey**: Reward function to use, defaults to "occupancy"
- **--[c]configfile**: Path to JSON file containing all parameters to be tuned as well as their ranges
- **--[n]etlogo_[p]ath**: Path to NetLogo installation (for Linux users only)
- **--[r]uns-per-round**: Comma-separated number of runs per optimization round, each with a successively smaller number of candidates, defaults to 1,2,5,10
- **[s]election-factor**: Selection factor n, meaning that one out of n candidates in each round advances to the next optimization round, defaults to 3