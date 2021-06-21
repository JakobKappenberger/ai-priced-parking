# Copyright 2020 Tensorforce Team. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

from collections import OrderedDict

from tensorforce import TensorforceError
from tensorforce.agents import TensorforceAgent


class ProximalPolicyOptimization(TensorforceAgent):
    """
    [Proximal Policy Optimization](https://arxiv.org/abs/1707.06347) agent (specification key:
    `ppo`).

    Args:
        states (specification): States specification
            (<span style="color:#C00000"><b>required</b></span>, better implicitly specified via
            `environment` argument for `Agent.create(...)`), arbitrarily nested dictionary of state
            descriptions (usually taken from `Environment.states()`) with the following attributes:
            <ul>
            <li><b>type</b> (<i>"bool" | "int" | "float"</i>) &ndash; state data type
            (<span style="color:#00C000"><b>default</b></span>: "float").</li>
            <li><b>shape</b> (<i>int | iter[int]</i>) &ndash; state shape
            (<span style="color:#C00000"><b>required</b></span>).</li>
            <li><b>num_values</b> (<i>int > 0</i>) &ndash; number of discrete state values
            (<span style="color:#C00000"><b>required</b></span> for type "int").</li>
            <li><b>min_value/max_value</b> (<i>float</i>) &ndash; minimum/maximum state value
            (<span style="color:#00C000"><b>optional</b></span> for type "float").</li>
            </ul>
        actions (specification): Actions specification
            (<span style="color:#C00000"><b>required</b></span>, better implicitly specified via
            `environment` argument for `Agent.create(...)`), arbitrarily nested dictionary of
            action descriptions (usually taken from `Environment.actions()`) with the following
            attributes:
            <ul>
            <li><b>type</b> (<i>"bool" | "int" | "float"</i>) &ndash; action data type
            (<span style="color:#C00000"><b>required</b></span>).</li>
            <li><b>shape</b> (<i>int > 0 | iter[int > 0]</i>) &ndash; action shape
            (<span style="color:#00C000"><b>default</b></span>: scalar).</li>
            <li><b>num_values</b> (<i>int > 0</i>) &ndash; number of discrete action values
            (<span style="color:#C00000"><b>required</b></span> for type "int").</li>
            <li><b>min_value/max_value</b> (<i>float</i>) &ndash; minimum/maximum action value
            (<span style="color:#00C000"><b>optional</b></span> for type "float").</li>
            </ul>
        max_episode_timesteps (int > 0): Upper bound for numer of timesteps per episode
            (<span style="color:#00C000"><b>default</b></span>: not given, better implicitly
            specified via `environment` argument for `Agent.create(...)`).

        batch_size (<a href="../modules/parameters.html">parameter</a>, int > 0): Number of episodes
            per update batch
            (<span style="color:#C00000"><b>required</b></span>).

        network ("auto" | specification): Policy network configuration, see the
            [networks documentation](../modules/networks.html)
            (<span style="color:#00C000"><b>default</b></span>: "auto", automatically configured
            network).
        use_beta_distribution (bool): Whether to use the Beta distribution for bounded continuous
            actions by default.
            (<span style="color:#00C000"><b>default</b></span>: false).

        memory (int > 0): Batch memory capacity, has to fit at least maximum batch_size + 1 episodes
            (<span style="color:#00C000"><b>default</b></span>: minimum capacity, usually does not
            need to be changed).

        update_frequency ("never" | <a href="../modules/parameters.html">parameter</a>, int > 0 | 0.0 < float <= 1.0):
            Frequency of updates, relative to batch_size if float
            (<span style="color:#00C000"><b>default</b></span>: batch_size).
        learning_rate (<a href="../modules/parameters.html">parameter</a>, float > 0.0): Optimizer
            learning rate
            (<span style="color:#00C000"><b>default</b></span>: 1e-3).
        multi_step (<a href="../modules/parameters.html">parameter</a>, int >= 1): Number of
            optimization steps, update_frequency * multi_step should be at least 1 if relative
            subsampling_fraction
            (<span style="color:#00C000"><b>default</b></span>: 10).
        subsampling_fraction (<a href="../modules/parameters.html">parameter</a>, int > 0 | 0.0 < float <= 1.0):
            Absolute/relative fraction of batch timesteps to subsample,
            update_frequency * multi_step should be at least 1 if relative subsampling_fraction
            (<span style="color:#00C000"><b>default</b></span>: 0.33).

        likelihood_ratio_clipping (<a href="../modules/parameters.html">parameter</a>, float > 0.0):
            Likelihood-ratio clipping threshold
            (<span style="color:#00C000"><b>default</b></span>: 0.25).
        discount (<a href="../modules/parameters.html">parameter</a>, 0.0 <= float <= 1.0): Discount
            factor for future rewards of discounted-sum reward estimation
            (<span style="color:#00C000"><b>default</b></span>: 0.99).
        return_processing (specification): Return processing as layer or list of layers, see the
            [preprocessing documentation](../modules/preprocessing.html)
            (<span style="color:#00C000"><b>default</b></span>: no return processing).
        advantage_processing (specification): Advantage processing as layer or list of layers, see
            the [preprocessing documentation](../modules/preprocessing.html)
            (<span style="color:#00C000"><b>default</b></span>: no advantage processing).
        predict_terminal_values (bool): Whether to predict the value of terminal states, usually
            not required since max_episode_timesteps terminals are handled separately
            (<span style="color:#00C000"><b>default</b></span>: false).

        baseline (specification): Baseline network configuration, see the
            [networks documentation](../modules/networks.html),
            main policy will be used as baseline if none
            (<span style="color:#00C000"><b>default</b></span>: none).
        baseline_optimizer (float > 0.0 | specification): Baseline optimizer configuration, see the
            [optimizers documentation](../modules/optimizers.html), main optimizer will be used for
            baseline if none, a float implies none and specifies a custom weight for the baseline
            loss
            (<span style="color:#00C000"><b>default</b></span>: none).

        l2_regularization (<a href="../modules/parameters.html">parameter</a>, float >= 0.0):
            L2 regularization loss weight
            (<span style="color:#00C000"><b>default</b></span>: no L2 regularization).
        entropy_regularization (<a href="../modules/parameters.html">parameter</a>, float >= 0.0):
            Entropy regularization loss weight, to discourage the policy distribution from being
            "too certain"
            (<span style="color:#00C000"><b>default</b></span>: no entropy regularization).

        state_preprocessing (dict[specification]): State preprocessing as layer or list of layers,
            see the [preprocessing documentation](../modules/preprocessing.html),
            specified per state-type or -name
            (<span style="color:#00C000"><b>default</b></span>: linear normalization of bounded
            float states to [-2.0, 2.0]).
        reward_preprocessing (specification): Reward preprocessing as layer or list of layers,
            see the [preprocessing documentation](../modules/preprocessing.html)
            (<span style="color:#00C000"><b>default</b></span>: no reward preprocessing).
        exploration (<a href="../modules/parameters.html">parameter</a> | dict[<a href="../modules/parameters.html">parameter</a>], float >= 0.0):
            Exploration, defined as the probability for uniformly random output in case of `bool`
            and `int` actions, and the standard deviation of Gaussian noise added to every output in
            case of `float` actions, specified globally or per action-type or -name
            (<span style="color:#00C000"><b>default</b></span>: no exploration).
        variable_noise (<a href="../modules/parameters.html">parameter</a>, float >= 0.0):
            Add Gaussian noise with given standard deviation to all trainable variables, as
            alternative exploration mechanism
            (<span style="color:#00C000"><b>default</b></span>: no variable noise).<br/><br/>

        >>>: For arguments below, see the [Tensorforce agent documentation](tensorforce.html).
        parallel_interactions (int > 0)
        config (specification)
        saver (path | specification)
        summarizer (path | specification)
        tracking ("all" | iter[string])
        recorder (path | specification)
    """

    def __init__(
        # Required
        self, states, actions, max_episode_timesteps, batch_size,
        # Network
        network='auto', use_beta_distribution=False,
        # Memory
        memory='minimum',
        # Optimization
        update_frequency=1.0, learning_rate=1e-3, multi_step=10, subsampling_fraction=0.33,
        # Reward estimation
        likelihood_ratio_clipping=0.25, discount=0.99, return_processing=None,
        advantage_processing=None, predict_terminal_values=False,
        # Baseline
        baseline=None, baseline_optimizer=None,
        # Preprocessing
        state_preprocessing='linear_normalization', reward_preprocessing=None,
        # Exploration
        exploration=0.0, variable_noise=0.0,
        # Regularization
        l2_regularization=0.0, entropy_regularization=0.0,
        # Parallel interactions
        parallel_interactions=1,
        # Config, saver, summarizer, tracking, recorder
        config=None, saver=None, summarizer=None, tracking=None, recorder=None,
        # Deprecated
        **kwargs
    ):
        if 'optimization_steps' in kwargs:
            raise TensorforceError.deprecated(
                name='PPO', argument='optimization_steps', replacement='multi_step'
            )
        if 'estimate_terminal' in kwargs:
            raise TensorforceError.deprecated(
                name='PPO', argument='estimate_terminal', replacement='predict_terminal_values'
            )
        if 'critic_network' in kwargs:
            raise TensorforceError.deprecated(
                name='PPO', argument='critic_network', replacement='baseline'
            )
        if 'baseline_network' in kwargs:
            raise TensorforceError.deprecated(
                name='PPO', argument='baseline_network', replacement='baseline'
            )
        if 'critic_optimizer' in kwargs:
            raise TensorforceError.deprecated(
                name='PPO', argument='critic_optimizer', replacement='baseline_optimizer'
            )

        self.spec = OrderedDict(
            agent='ppo',
            states=states, actions=actions, max_episode_timesteps=max_episode_timesteps,
            batch_size=batch_size,
            network=network, use_beta_distribution=use_beta_distribution,
            memory=memory,
            update_frequency=update_frequency, learning_rate=learning_rate,
            multi_step=multi_step, subsampling_fraction=subsampling_fraction,
            likelihood_ratio_clipping=likelihood_ratio_clipping, discount=discount,
            return_processing=return_processing, advantage_processing=advantage_processing,
            predict_terminal_values=predict_terminal_values,
            baseline=baseline, baseline_optimizer=baseline_optimizer,
            state_preprocessing=state_preprocessing, reward_preprocessing=reward_preprocessing,
            exploration=exploration, variable_noise=variable_noise,
            l2_regularization=l2_regularization, entropy_regularization=entropy_regularization,
            parallel_interactions=parallel_interactions,
            config=config, saver=saver, summarizer=summarizer, tracking=tracking, recorder=recorder
        )

        policy = dict(
            type='parametrized_distributions', network=network, temperature=1.0,
            use_beta_distribution=use_beta_distribution
        )

        if memory == 'minimum':
            memory = dict(type='recent')
        else:
            memory = dict(type='recent', capacity=memory)

        update = dict(unit='episodes', batch_size=batch_size, frequency=update_frequency)

        optimizer = dict(
            optimizer='adam', learning_rate=learning_rate, multi_step=multi_step,
            subsampling_fraction=subsampling_fraction
        )
        objective = dict(
            type='policy_gradient', importance_sampling=True,
            clipping_value=likelihood_ratio_clipping
        )

        if baseline is None:
            assert not predict_terminal_values
            reward_estimation = dict(
                horizon='episode', discount=discount, predict_horizon_values=False,
                estimate_advantage=False, return_processing=return_processing
            )
            assert baseline_optimizer is None
            baseline_objective = None

        else:
            reward_estimation = dict(
                horizon='episode', discount=discount, predict_horizon_values='early',
                estimate_advantage=True, predict_action_values=False,
                return_processing=return_processing, predict_terminal_values=predict_terminal_values
            )
            baseline = dict(type='parametrized_state_value', network=baseline)
            assert baseline_optimizer is not None
            baseline_objective = dict(type='state_value')

        super().__init__(
            # Agent
            states=states, actions=actions, max_episode_timesteps=max_episode_timesteps,
            parallel_interactions=parallel_interactions, config=config, recorder=recorder,
            # TensorforceModel
            policy=policy, memory=memory, update=update, optimizer=optimizer, objective=objective,
            reward_estimation=reward_estimation,
            baseline=baseline, baseline_optimizer=baseline_optimizer,
            baseline_objective=baseline_objective,
            l2_regularization=l2_regularization, entropy_regularization=entropy_regularization,
            state_preprocessing=state_preprocessing, reward_preprocessing=reward_preprocessing,
            exploration=exploration, variable_noise=variable_noise,
            saver=saver, summarizer=summarizer, tracking=tracking, **kwargs
        )
