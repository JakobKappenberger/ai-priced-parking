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

import logging

import tensorflow as tf

from tensorforce import TensorforceError
from tensorforce.core import ModuleDict, memory_modules, optimizer_modules, parameter_modules, \
    SignatureDict, TensorDict, TensorSpec, TensorsSpec, tf_function, tf_util, VariableDict
from tensorforce.core.models import Model
from tensorforce.core.networks import Preprocessor
from tensorforce.core.objectives import objective_modules
from tensorforce.core.policies import policy_modules, StochasticPolicy


class TensorforceModel(Model):

    def __init__(
        self, *,
        states, actions, max_episode_timesteps,
        policy, memory, update, optimizer, objective, reward_estimation,
        baseline, baseline_optimizer, baseline_objective,
        l2_regularization, entropy_regularization,
        state_preprocessing, reward_preprocessing,
        exploration, variable_noise,
        parallel_interactions,
        config, saver, summarizer, tracking
    ):
        super().__init__(
            states=states, actions=actions, l2_regularization=l2_regularization,
            parallel_interactions=parallel_interactions, config=config, saver=saver,
            summarizer=summarizer, tracking=tracking
        )

        if max_episode_timesteps is None:
            self.max_episode_timesteps = None
        else:
            self.max_episode_timesteps = int(max_episode_timesteps)

        # State preprocessing
        self.processed_states_spec = TensorsSpec()
        self.state_preprocessing = ModuleDict()
        if state_preprocessing == 'linear_normalization':
            # Default handling, otherwise layer will be applied to all input types
            state_preprocessing = None
        if not isinstance(state_preprocessing, dict) or \
                any(name not in self.states_spec for name in state_preprocessing):
            state_preprocessing = {name: state_preprocessing for name in self.states_spec}

        for name, spec in self.states_spec.items():
            if name in state_preprocessing:
                layers = state_preprocessing[name]
            elif spec.type in state_preprocessing:
                layers = state_preprocessing[spec.type]
            else:
                layers = None

            # Normalize bounded inputs to [-2.0, 2.0]
            if spec.type == 'float' and spec.min_value is not None and \
                    spec.max_value is not None and layers is None:
                layers = ['linear_normalization']

            if layers is None:
                self.processed_states_spec[name] = self.states_spec[name]
            else:
                if name is None:
                    module_name = 'state_preprocessing'
                else:
                    module_name = name + '_preprocessing'
                self.state_preprocessing[name] = self.submodule(
                    name=module_name, module=Preprocessor, is_trainable=False, input_spec=spec,
                    layers=layers
                )
                spec = self.state_preprocessing[name].output_spec()
                self.processed_states_spec[name] = spec

            if spec.type == 'float' and spec.min_value is not None and \
                    spec.max_value is not None:
                if isinstance(spec.min_value, float):
                    if not (-10.0 <= spec.min_value < 0.0) or not (0.0 < spec.max_value <= 10.0):
                        logging.warning("{}tate{} does not seem to be normalized, consider "
                                        "adding linear_normalization preprocessing.".format(
                                            'S' if layers is None else 'Preprocessed s',
                                            '' if name is None else ' ' + name
                                        ))
                else:
                    # TODO: missing +/-10.0 check, but cases of values +/-inf are already covered by
                    # previous no-bound warning
                    if (spec.min_value >= 0.0).any() or (spec.max_value <= 0.0).any():
                        logging.warning("{}tate{} does not seem to be normalized, consider "
                                        "adding linear_normalization preprocessing.".format(
                                            'S' if layers is None else 'Preprocessed s',
                                            '' if name is None else ' ' + name
                                        ))

        # Reward preprocessing
        if reward_preprocessing is None:
            self.reward_preprocessing = None
        else:
            self.reward_preprocessing = self.submodule(
                name='reward_preprocessing', module=Preprocessor, is_trainable=False,
                input_spec=self.reward_spec, layers=reward_preprocessing
            )
            if self.reward_preprocessing.output_spec() != self.reward_spec:
                raise TensorforceError.mismatch(
                    name='reward_preprocessing', argument='output spec',
                    value1=self.reward_preprocessing.output_spec(), value2=self.reward_spec
                )

        # Action exploration
        if exploration is None:
            exploration = 0.0
        if isinstance(exploration, dict) and all(name in self.actions_spec for name in exploration):
            # Different exploration per action
            self.exploration = ModuleDict()
            for name, spec in self.actions_spec.items():
                if name in exploration:
                    module = exploration[name]
                elif spec.type in exploration:
                    module = exploration[spec.type]
                else:
                    module = None
                if module is None:
                    pass
                elif spec.type in ('bool', 'int'):
                    self.exploration[name] = self.submodule(
                        name=(name + '_exploration'), module=module, modules=parameter_modules,
                        is_trainable=False, dtype='float', min_value=0.0, max_value=1.0
                    )
                else:
                    self.exploration[name] = self.submodule(
                        name=(name + '_exploration'), module=module, modules=parameter_modules,
                        is_trainable=False, dtype='float', min_value=0.0
                    )
        else:
            # Same exploration for all actions
            self.exploration = self.submodule(
                name='exploration', module=exploration, modules=parameter_modules,
                is_trainable=False, dtype='float', min_value=0.0
            )

        # Variable noise
        if variable_noise is None:
            variable_noise = 0.0
        self.variable_noise = self.submodule(
            name='variable_noise', module=variable_noise, modules=parameter_modules,
            is_trainable=False, dtype='float', min_value=0.0
        )

        # Reward estimation argument check
        if not all(key in (
            'advantage_processing', 'discount', 'estimate_advantage', 'gae_decay', 'horizon',
            'predict_action_values', 'predict_horizon_values', 'predict_terminal_values',
            'return_processing', 'trace_decay'
        ) for key in reward_estimation):
            raise TensorforceError.value(
                name='agent', argument='reward_estimation', value=reward_estimation,
                hint='not from {advantage_processing,discount,estimate_advantage,gae_decay,'
                     'horizon,predict_action_values,predict_horizon_values,predict_terminal_values,'
                     'return_processing,trace_decay}'
            )

        # Reward estimation
        self.estimate_advantage = reward_estimation.get('estimate_advantage', False)
        self.predict_horizon_values = reward_estimation.get('predict_horizon_values')
        self.predict_action_values = reward_estimation.get('predict_action_values', False)
        self.predict_terminal_values = reward_estimation.get('predict_terminal_values', False)

        # Return horizon
        if reward_estimation['horizon'] == 'episode':
            self.reward_horizon = 'episode'
            if self.predict_horizon_values is None:
                self.predict_horizon_values = 'early'
            elif self.predict_horizon_values == 'late':
                raise TensorforceError.value(
                    name='agent', argument='reward_estimation[predict_horizon_values]',
                    value=self.predict_horizon_values,
                    condition='reward_estimation[reward_horizon] is "episode"'
                )
        else:
            self.reward_horizon = self.submodule(
                name='reward_horizon', module=reward_estimation['horizon'],
                modules=parameter_modules, dtype='int', min_value=1,
                max_value=self.max_episode_timesteps
            )
            if self.predict_horizon_values is None:
                self.predict_horizon_values = 'late'

        # Reward discount
        reward_discount = reward_estimation.get('discount')
        if reward_discount is None:
            reward_discount = 1.0
        self.reward_discount = self.submodule(
            name='reward_discount', module=reward_discount, modules=parameter_modules,
            dtype='float', min_value=0.0, max_value=1.0
        )

        # Entropy regularization
        if entropy_regularization is None:
            entropy_regularization = 0.0
        self.entropy_regularization = self.submodule(
            name='entropy_regularization', module=entropy_regularization,
            modules=parameter_modules, is_trainable=False, dtype='float', min_value=0.0
        )

        # Update mode
        if not all(key in ('batch_size', 'frequency', 'start', 'unit') for key in update):
            raise TensorforceError.value(
                name='agent', argument='update', value=list(update),
                hint='not from {batch_size,frequency,start,unit}'
            )
        # update: unit
        elif 'unit' not in update:
            raise TensorforceError.required(name='agent', argument='update[unit]')
        elif update['unit'] not in ('timesteps', 'episodes'):
            raise TensorforceError.value(
                name='agent', argument='update[unit]', value=update['unit'],
                hint='not in {timesteps,episodes}'
            )
        # update: batch_size
        elif 'batch_size' not in update:
            raise TensorforceError.required(name='agent', argument='update[batch_size]')

        self.update_unit = update['unit']
        self.update_batch_size = self.submodule(
            name='update_batch_size', module=update['batch_size'], modules=parameter_modules,
            is_trainable=False, dtype='int', min_value=1
        )
        if 'frequency' in update and update['frequency'] == 'never':
            self.update_frequency = None
        else:
            frequency = update.get('frequency')
            if frequency is None:
                frequency = update['batch_size']
            elif isinstance(frequency, float):
                if frequency <= 0.0 or frequency > 1.0:
                    raise TensorforceError.value(
                        name='agent', argument='update[frequency]', value=update['frequency'],
                        hint='not in (0.0, 1.0]'
                    )
                else:
                    frequency = max(1, int(frequency * update['batch_size']))
            self.update_frequency = self.submodule(
                name='update_frequency', module=frequency, modules=parameter_modules,
                is_trainable=False, dtype='int', min_value=1,
                max_value=max(2, self.update_batch_size.max_value())
            )
            start = update.get('start')
            if start is None:
                start = 0
            self.update_start = self.submodule(
                name='update_start', module=start, modules=parameter_modules, is_trainable=False,
                dtype='int', min_value=0
            )

        # Baseline optimization overview:
        # Policy    Objective   Optimizer   Config
        #   n         n           n           default predict_horizon_values=False
        #   n         n           f           default predict_horizon=False
        #   n         n           y           default predict_horizon=False
        #   n         y           n           main policy, shared loss/kldiv, weighted 1.0
        #   n         y           f           main policy, shared loss/kldiv, weighted
        #   n         y           y           main policy, separate
        #   y         n           n           estimate_advantage=True,advantage_in_loss=True
        #   y         n           f           shared objective/loss/kldiv, weighted
        #   y         n           y           shared objective
        #   y         y           n           shared loss/kldiv, weighted 1.0, equal horizon
        #   y         y           f           shared loss/kldiv, weighted, equal horizon
        #   y         y           y           separate

        self.separate_baseline = (baseline is not None)

        if baseline is None and baseline_objective is None and \
                'predict_horizon_values' not in reward_estimation:
            self.predict_horizon_values = False

        if baseline is not None and baseline_objective is None and \
                baseline_optimizer is None:
            if 'estimate_advantage' not in reward_estimation:
                self.estimate_advantage = True
            self.advantage_in_loss = True
        else:
            self.advantage_in_loss = False

        if baseline_optimizer is None and baseline_objective is not None:
            baseline_optimizer = 1.0

        if baseline_optimizer is None or isinstance(baseline_optimizer, float):
            baseline_is_trainable = True
        else:
            baseline_is_trainable = False

        # Return processing
        return_processing = reward_estimation.get('return_processing')
        if return_processing is None:
            self.return_processing = None
        else:
            self.return_processing = self.submodule(
                name='return_processing', module=Preprocessor, is_trainable=False,
                input_spec=self.reward_spec, layers=return_processing,
                is_preprocessing_layer_valid=False
            )
            if self.return_processing.output_spec() != self.reward_spec:
                raise TensorforceError.mismatch(
                    name='reward_estimation[return_processing]', argument='output spec',
                    value1=self.return_processing.output_spec(), value2=self.reward_spec
                )

        # Advantage processing
        advantage_processing = reward_estimation.get('advantage_processing')
        if advantage_processing is None:
            self.advantage_processing = None
        else:
            if self.estimate_advantage is False:
                raise TensorforceError.invalid(
                    name='agent', argument='reward_estimation[advantage_processing]',
                    condition='reward_estimation[estimate_advantage] is false'
                )
            self.advantage_processing = self.submodule(
                name='advantage_processing', module=Preprocessor, is_trainable=False,
                input_spec=self.reward_spec, layers=advantage_processing,
                is_preprocessing_layer_valid=False
            )
            if self.advantage_processing.output_spec() != self.reward_spec:
                raise TensorforceError.mismatch(
                    name='reward_estimation[advantage_processing]', argument='output spec',
                    value1=self.advantage_processing.output_spec(), value2=self.reward_spec
                )

        # Objectives
        self.objective = self.submodule(
            name='policy_objective', module=objective, modules=objective_modules,
            states_spec=self.processed_states_spec, auxiliaries_spec=self.auxiliaries_spec,
            actions_spec=self.actions_spec, reward_spec=self.reward_spec
        )
        if baseline_objective is None:
            self.baseline_objective = None
        else:
            self.baseline_objective = self.submodule(
                name='baseline_objective', module=baseline_objective, modules=objective_modules,
                is_trainable=baseline_is_trainable, states_spec=self.processed_states_spec,
                auxiliaries_spec=self.auxiliaries_spec, actions_spec=self.actions_spec,
                reward_spec=self.reward_spec
            )
            assert len(self.baseline_objective.required_baseline_fns()) == 0

        # Policy
        required_fns = {'policy'}
        required_fns.update(self.objective.required_policy_fns())
        if not self.separate_baseline:
            if self.predict_horizon_values is not False or self.estimate_advantage is not False:
                if self.predict_action_values:
                    required_fns.add('action_value')
                else:
                    required_fns.add('state_value')
            required_fns.update(self.objective.required_baseline_fns())
            if self.baseline_objective is not None:
                required_fns.update(self.baseline_objective.required_policy_fns())

        if required_fns <= {'state_value'}:
            default_module = 'parametrized_state_value'
        elif required_fns <= {'action_value'} and \
                all(spec.type == 'float' for spec in self.actions_spec.values()):
            default_module = 'parametrized_action_value'
        elif required_fns <= {'policy', 'action_value', 'state_value'} and \
                all(spec.type in ('bool', 'int') for spec in self.actions_spec.values()):
            default_module = 'parametrized_value_policy'
        elif required_fns <= {'policy', 'stochastic'}:
            default_module = 'parametrized_distributions'
        else:
            logging.warning(
                "Policy type should be explicitly specified for non-standard agent configuration."
            )
            default_module = 'parametrized_distributions'

        self.policy = self.submodule(
            name='policy', module=policy, modules=policy_modules, default_module=default_module,
            states_spec=self.processed_states_spec, auxiliaries_spec=self.auxiliaries_spec,
            actions_spec=self.actions_spec
        )
        self.internals_spec['policy'] = self.policy.internals_spec
        self.initial_internals['policy'] = self.policy.internals_init()
        self.objective.internals_spec = self.policy.internals_spec

        if not self.entropy_regularization.is_constant(value=0.0) and \
                not isinstance(self.policy, StochasticPolicy):
            raise TensorforceError.invalid(
                name='agent', argument='entropy_regularization',
                condition='policy is not stochastic'
            )

        # Baseline
        if self.separate_baseline:
            if self.predict_horizon_values is not False or self.estimate_advantage is not False:
                if self.predict_action_values:
                    required_fns = {'action_value'}
                else:
                    required_fns = {'state_value'}
            required_fns.update(self.objective.required_baseline_fns())
            if self.baseline_objective is not None:
                required_fns.update(self.baseline_objective.required_policy_fns())

            if required_fns <= {'state_value'}:
                default_module = 'parametrized_state_value'
            elif required_fns <= {'action_value'} and \
                    all(spec.type == 'float' for spec in self.actions_spec.values()):
                default_module = 'parametrized_action_value'
            elif required_fns <= {'policy', 'action_value', 'state_value'} and \
                    all(spec.type in ('bool', 'int') for spec in self.actions_spec.values()):
                default_module = 'parametrized_value_policy'
            elif required_fns <= {'policy', 'stochastic'}:
                default_module = 'parametrized_distributions'
            else:
                logging.warning("Policy type should be explicitly specified for non-standard agent "
                                "configuration.")
                default_module = 'parametrized_distributions'

            self.baseline = self.submodule(
                name='baseline', module=baseline, modules=policy_modules,
                default_module=default_module, is_trainable=baseline_is_trainable,
                states_spec=self.processed_states_spec, auxiliaries_spec=self.auxiliaries_spec,
                actions_spec=self.actions_spec
            )
            self.internals_spec['baseline'] = self.baseline.internals_spec
            self.initial_internals['baseline'] = self.baseline.internals_init()

        else:
            self.baseline = self.policy

        if self.baseline_objective is not None:
            self.baseline_objective.internals_spec = self.baseline.internals_spec

        # Check for name collisions
        for name in self.internals_spec:
            if name in self.value_names:
                raise TensorforceError.exists(name='value name', value=name)
            self.value_names.add(name)

        # Optimizers
        if baseline_optimizer is None:
            self.baseline_loss_weight = None
            internals_spec = self.internals_spec
            self.baseline_optimizer = None
        elif isinstance(baseline_optimizer, float):
            self.baseline_loss_weight = self.submodule(
                name='baseline_loss_weight', module=baseline_optimizer, modules=parameter_modules,
                is_trainable=False, dtype='float', min_value=0.0
            )
            internals_spec = self.internals_spec
            self.baseline_optimizer = None
        else:
            self.baseline_loss_weight = None
            internals_spec = self.internals_spec['policy']
            if self.separate_baseline:
                baseline_internals = self.internals_spec['baseline']
            else:
                baseline_internals = self.internals_spec['policy']
            arguments_spec = TensorsSpec(
                states=self.processed_states_spec, horizons=TensorSpec(type='int', shape=(2,)),
                internals=baseline_internals, auxiliaries=self.auxiliaries_spec,
                actions=self.actions_spec, reward=self.reward_spec
            )
            if self.baseline_objective is not None:
                arguments_spec['reference'] = self.baseline_objective.reference_spec()
            self.baseline_optimizer = self.submodule(
                name='baseline_optimizer', module=baseline_optimizer, modules=optimizer_modules,
                is_trainable=False, arguments_spec=arguments_spec
            )
        arguments_spec = TensorsSpec(
            states=self.processed_states_spec, horizons=TensorSpec(type='int', shape=(2,)),
            internals=internals_spec, auxiliaries=self.auxiliaries_spec, actions=self.actions_spec,
            reward=self.reward_spec
        )
        if self.baseline_objective is not None and self.baseline_loss_weight is not None and \
                not self.baseline_loss_weight.is_constant(value=0.0):
            arguments_spec['reference'] = TensorsSpec(
                policy=self.objective.reference_spec(),
                baseline=self.baseline_objective.reference_spec()
            )
        else:
            arguments_spec['reference'] = self.objective.reference_spec()
        self.optimizer = self.submodule(
            name='policy_optimizer', module=optimizer, modules=optimizer_modules,
            arguments_spec=arguments_spec
        )

        # Memory
        values_spec = TensorsSpec(
            states=self.processed_states_spec, internals=self.internals_spec,
            auxiliaries=self.auxiliaries_spec, actions=self.actions_spec,
            terminal=self.terminal_spec, reward=self.reward_spec
        )
        if self.update_unit == 'timesteps':
            max_past_horizon = max(
                self.policy.max_past_horizon(on_policy=False),
                self.baseline.max_past_horizon(on_policy=False)
            )
            min_capacity = self.update_batch_size.max_value() + 1 + max_past_horizon
            if self.reward_horizon == 'episode':
                min_capacity += self.max_episode_timesteps
            else:
                min_capacity += self.reward_horizon.max_value()
            if self.max_episode_timesteps is not None:
                min_capacity = max(min_capacity, self.max_episode_timesteps)
        elif self.update_unit == 'episodes':
            if self.max_episode_timesteps is None:
                min_capacity = None
            else:
                min_capacity = (self.update_batch_size.max_value() + 1) * self.max_episode_timesteps
        else:
            assert False
        if self.config.buffer_observe == 'episode':
            if self.max_episode_timesteps is not None:
                min_capacity = max(min_capacity, 2 * self.max_episode_timesteps)
        elif isinstance(self.config.buffer_observe, int):
            if min_capacity is None:
                min_capacity = 2 * self.config.buffer_observe
            else:
                min_capacity = max(min_capacity, 2 * self.config.buffer_observe)

        self.memory = self.submodule(
            name='memory', module=memory, modules=memory_modules, is_trainable=False,
            values_spec=values_spec, min_capacity=min_capacity
        )

        # Trace decay
        trace_decay = reward_estimation.get('trace_decay', 1.0)
        if trace_decay != 1.0 and self.predict_horizon_values != 'early':
            raise TensorforceError.invalid(
                name='agent', argument='reward_estimation[trace_decay]',
                condition='reward_estimation[predict_horizon_values] != "early"'
            )
        self.trace_decay = self.submodule(
            name='trace_decay', module=trace_decay, modules=parameter_modules, dtype='float',
            min_value=0.0, max_value=1.0
        )

        # GAE decay
        gae_decay = reward_estimation.get('gae_decay', 0.0)
        if gae_decay != 0.0:
            from tensorforce.core.memories import Recent
            if not isinstance(self.memory, Recent):
                raise TensorforceError.invalid(
                    name='agent', argument='reward_estimation[gae_decay]',
                    condition='memory type is not Recent'
                )
            elif self.estimate_advantage is False:
                raise TensorforceError.invalid(
                    name='agent', argument='reward_estimation[gae_decay]',
                    condition='reward_estimation[estimate_advantage] is false'
                )
            elif self.advantage_in_loss:
                raise TensorforceError.invalid(
                    name='agent', argument='reward_estimation[gae_decay]',
                    condition='advantage-in-loss mode'
                )
        self.gae_decay = self.submodule(
            name='gae_decay', module=gae_decay, modules=parameter_modules, dtype='float',
            min_value=0.0, max_value=1.0
        )

    def get_architecture(self):
        if self.state_preprocessing.is_singleton():
            architecture = 'State-preprocessing:  {}\n'.format(
                self.state_preprocessing.singleton().get_architecture().replace('\n', '\n    ')
            )
        else:
            architecture = ''
            for name, preprocessor in self.state_preprocessing.items():
                architecture += '    {}:  {}\n'.format(
                    name, preprocessor.get_architecture().replace('\n', '\n    ')
                )
            if len(architecture) > 0:
                architecture = 'State-preprocessing:\n' + architecture
        architecture = 'Policy:\n    {}'.format(
            self.policy.get_architecture().replace('\n', '\n    ')
        )
        if self.separate_baseline:
            architecture += '\nBaseline:\n    {}'.format(
                self.baseline.get_architecture().replace('\n', '\n    ')
            )
        elif self.predict_horizon_values or self.baseline_objective is not None:
            architecture += '\nBaseline:  policy used as baseline'
        return architecture

    def initialize(self):
        super().initialize()

        # Initial variables summaries
        if self.summaries == 'all' or 'variables' in self.summaries:
            with self.summarizer.as_default():
                for variable in self.trainable_variables:
                    name = variable.name
                    assert name.startswith(self.name + '/') and name[-2:] == ':0'
                    # Add prefix self.name since otherwise different scope from later summaries
                    name = self.name + '/variables/' + name[len(self.name) + 1: -2]
                    x = tf.math.reduce_mean(input_tensor=variable)
                    tf.summary.scalar(name=name, data=x, step=self.updates)

    def core_initialize(self):
        super().core_initialize()

        # Preprocessed episode reward
        if self.reward_preprocessing is not None:
            self.preprocessed_episode_return = self.variable(
                name='preprocessed-episode-return',
                spec=TensorSpec(type=self.reward_spec.type, shape=(self.parallel_interactions,)),
                initializer='zeros', is_trainable=False, is_saved=False
            )

        # Buffer index
        self.buffer_index = self.variable(
            name='buffer-index', spec=TensorSpec(type='int', shape=(self.parallel_interactions,)),
            initializer='zeros', is_trainable=False, is_saved=False
        )

        if self.reward_horizon == 'episode' or self.parallel_interactions > 1 or \
                self.config.buffer_observe == 'episode':
            capacity = self.max_episode_timesteps
        else:
            capacity = self.config.buffer_observe + self.reward_horizon.max_value()
            if self.max_episode_timesteps is not None:
                capacity = min(capacity, self.max_episode_timesteps)

        # States/internals/auxiliaries/actions buffers
        def function(name, spec):
            shape = (self.parallel_interactions, capacity) + spec.shape
            return self.variable(
                name=(name + '-buffer'), spec=TensorSpec(type=spec.type, shape=shape),
                initializer='zeros', is_trainable=False, is_saved=False
            )

        self.states_buffer = self.processed_states_spec.fmap(
            function=function, cls=VariableDict, with_names='states'
        )
        self.internals_buffer = self.internals_spec.fmap(
            function=function, cls=VariableDict, with_names=True
        )
        self.auxiliaries_buffer = self.auxiliaries_spec.fmap(
            function=function, cls=VariableDict, with_names='action'
        )
        self.actions_buffer = self.actions_spec.fmap(
            function=function, cls=VariableDict, with_names='actions'
        )

        # Terminal/reward buffer
        if self.config.buffer_observe != 'episode':
            self.terminal_buffer = function('terminal', self.terminal_spec)
            self.reward_buffer = function('reward', self.reward_spec)

        # Buffer start
        if self.reward_horizon != 'episode' and self.parallel_interactions == 1 and \
                self.config.buffer_observe != 'episode':
            self.circular_buffer = True
            self.buffer_capacity = capacity
            self.buffer_start = self.variable(
                name='buffer-start',
                spec=TensorSpec(type='int', shape=(self.parallel_interactions,)),
                initializer='zeros', is_trainable=False, is_saved=False
            )
        else:
            self.circular_buffer = False

        # Last update
        self.last_update = self.variable(
            name='last-update', spec=TensorSpec(type='int'),
            initializer=-self.update_frequency.max_value(), is_trainable=False, is_saved=True
        )

        # Optimizer initialize given variables
        if self.advantage_in_loss:
            self.optimizer.initialize_given_variables(variables=self.trainable_variables)
        else:
            self.optimizer.initialize_given_variables(variables=self.policy.trainable_variables)
        if self.baseline_optimizer is not None:
            self.baseline_optimizer.initialize_given_variables(
                variables=self.baseline.trainable_variables
            )

        # Summaries and tracking
        self.register_summary(label='loss', name='losses/policy-objective-loss')
        self.register_tracking(
            label='loss', name='policy-objective-loss', spec=TensorSpec(type='float')
        )
        self.register_summary(label='loss', name='losses/policy-regularization-loss')
        self.register_tracking(
            label='loss', name='policy-regularization-loss', spec=TensorSpec(type='float')
        )
        self.register_summary(label='loss', name='losses/policy-loss')
        self.register_tracking(label='loss', name='policy-loss', spec=TensorSpec(type='float'))
        if self.baseline_optimizer is not None or (
            self.baseline_loss_weight is not None and
            not self.baseline_loss_weight.is_constant(value=0.0)
        ):
            self.register_summary(label='loss', name='losses/baseline-loss')
            self.register_tracking(label='loss', name='baseline-loss', spec=TensorSpec(type='float'))
            if self.separate_baseline:
                self.register_summary(label='loss', name='losses/baseline-objective-loss')
                self.register_tracking(
                    label='loss', name='baseline-objective-loss', spec=TensorSpec(type='float')
                )
                self.register_summary(label='loss', name='losses/baseline-regularization-loss')
                self.register_tracking(
                    label='loss', name='baseline-regularization-loss',
                    spec=TensorSpec(type='float')
                )

        if self.reward_preprocessing is not None:
            self.register_tracking(
                label='reward', name='preprocessed-reward', spec=TensorSpec(type='float')
            )
            self.register_tracking(
                label='reward', name='preprocessed-episode-return', spec=TensorSpec(type='float')
            )
        self.register_tracking(label='reward', name='update-return', spec=TensorSpec(type='float'))
        if self.return_processing is not None:
            self.register_tracking(
                label='reward', name='update-processed-return', spec=TensorSpec(type='float')
            )
        if self.estimate_advantage is not False:
            self.register_tracking(
                label='reward', name='update-advantage', spec=TensorSpec(type='float')
            )
            if self.advantage_processing is not None:
                self.register_tracking(
                    label='reward', name='update-processed-advantage',
                    spec=TensorSpec(type='float')
                )
        if not self.gae_decay.is_constant(value=0.0):
            self.register_tracking(
                label='reward', name='update-gae', spec=TensorSpec(type='float')
            )

        self.register_tracking(label='entropy', name='entropy', spec=TensorSpec(type='float'))
        self.register_tracking(
            label='kl-divergence', name='kl-divergence', spec=TensorSpec(type='float')
        )
        if len(self.actions_spec) > 1:
            for name in self.actions_spec:
                self.register_tracking(
                    label='entropy', name=('entropies/' + name), spec=TensorSpec(type='float')
                )
                self.register_tracking(
                    label='kl-divergence', name=('kl-divergences/' + name),
                    spec=TensorSpec(type='float')
                )

    def initialize_api(self):
        super().initialize_api()

        if 'graph' in self.summaries:
            tf.summary.trace_on(graph=True, profiler=False)
        self.experience(
            states=self.states_spec, internals=self.internals_spec,
            auxiliaries=self.auxiliaries_spec, actions=self.actions_spec,
            terminal=self.terminal_spec, reward=self.reward_spec, _initialize=True
        )
        if 'graph' in self.summaries:
            tf.summary.trace_export(name='experience', step=self.timesteps, profiler_outdir=None)
            tf.summary.trace_on(graph=True, profiler=False)
        self.update(_initialize=True)
        if 'graph' in self.summaries:
            tf.summary.trace_export(name='update', step=self.timesteps, profiler_outdir=None)

    def get_savedmodel_trackables(self):
        trackables = super().get_savedmodel_trackables()
        for name, trackable in self.policy.get_savedmodel_trackables().items():
            assert name not in trackables
            trackables[name] = trackable
        if self.separate_baseline and len(self.internals_spec['baseline']) > 0:
            for name, trackable in self.baseline.get_savedmodel_trackables().items():
                assert name not in trackables
                trackables[name] = trackable
        return trackables

    def input_signature(self, *, function):
        if function == 'baseline_loss':
            if self.separate_baseline:
                internals_signature = self.internals_spec['baseline'].signature(batched=True)
            else:
                internals_signature = self.internals_spec['policy'].signature(batched=True)
            if self.advantage_in_loss:
                assert False
            elif self.baseline_objective is None:
                return SignatureDict(
                    states=self.processed_states_spec.signature(batched=True),
                    horizons=TensorSpec(type='int', shape=(2,)).signature(batched=True),
                    internals=internals_signature,
                    auxiliaries=self.auxiliaries_spec.signature(batched=True),
                    actions=self.actions_spec.signature(batched=True),
                    reward=self.reward_spec.signature(batched=True),
                    reference=self.objective.reference_spec().signature(batched=True)
                )
            else:
                return SignatureDict(
                    states=self.processed_states_spec.signature(batched=True),
                    horizons=TensorSpec(type='int', shape=(2,)).signature(batched=True),
                    internals=internals_signature,
                    auxiliaries=self.auxiliaries_spec.signature(batched=True),
                    actions=self.actions_spec.signature(batched=True),
                    reward=self.reward_spec.signature(batched=True),
                    reference=self.baseline_objective.reference_spec().signature(batched=True)
                )

        elif function == 'core_experience':
            return SignatureDict(
                states=self.processed_states_spec.signature(batched=True),
                internals=self.internals_spec.signature(batched=True),
                auxiliaries=self.auxiliaries_spec.signature(batched=True),
                actions=self.actions_spec.signature(batched=True),
                terminal=self.terminal_spec.signature(batched=True),
                reward=self.reward_spec.signature(batched=True)
            )

        elif function == 'core_update':
            return SignatureDict()

        elif function == 'experience':
            return SignatureDict(
                states=self.states_spec.signature(batched=True),
                internals=self.internals_spec.signature(batched=True),
                auxiliaries=self.auxiliaries_spec.signature(batched=True),
                actions=self.actions_spec.signature(batched=True),
                terminal=self.terminal_spec.signature(batched=True),
                reward=self.reward_spec.signature(batched=True)
            )

        elif function == 'loss':
            if self.baseline_objective is not None and self.baseline_loss_weight is not None and \
                    not self.baseline_loss_weight.is_constant(value=0.0):
                return SignatureDict(
                    states=self.processed_states_spec.signature(batched=True),
                    horizons=TensorSpec(type='int', shape=(2,)).signature(batched=True),
                    internals=self.internals_spec.signature(batched=True),
                    auxiliaries=self.auxiliaries_spec.signature(batched=True),
                    actions=self.actions_spec.signature(batched=True),
                    reward=self.reward_spec.signature(batched=True),
                    reference=SignatureDict(
                        policy=self.objective.reference_spec().signature(batched=True),
                        baseline=self.baseline_objective.reference_spec().signature(batched=True)
                    )
                )
            elif self.baseline_optimizer is None:
                return SignatureDict(
                    states=self.processed_states_spec.signature(batched=True),
                    horizons=TensorSpec(type='int', shape=(2,)).signature(batched=True),
                    internals=self.internals_spec.signature(batched=True),
                    auxiliaries=self.auxiliaries_spec.signature(batched=True),
                    actions=self.actions_spec.signature(batched=True),
                    reward=self.reward_spec.signature(batched=True),
                    reference=self.objective.reference_spec().signature(batched=True)
                )
            else:
                return SignatureDict(
                    states=self.processed_states_spec.signature(batched=True),
                    horizons=TensorSpec(type='int', shape=(2,)).signature(batched=True),
                    internals=self.internals_spec['policy'].signature(batched=True),
                    auxiliaries=self.auxiliaries_spec.signature(batched=True),
                    actions=self.actions_spec.signature(batched=True),
                    reward=self.reward_spec.signature(batched=True),
                    reference=self.objective.reference_spec().signature(batched=True)
                )

        elif function == 'regularize':
            return SignatureDict(
                states=self.processed_states_spec.signature(batched=True),
                horizons=TensorSpec(type='int', shape=(2,)).signature(batched=True),
                internals=self.internals_spec['policy'].signature(batched=True),
                auxiliaries=self.auxiliaries_spec.signature(batched=True)
            )

        elif function == 'update':
            return SignatureDict()

        else:
            return super().input_signature(function=function)

    def output_signature(self, *, function):
        if function == 'baseline_loss':
            return SignatureDict(
                singleton=TensorSpec(type='float', shape=()).signature(batched=False)
            )

        elif function == 'core_experience':
            return SignatureDict(
                singleton=TensorSpec(type='bool', shape=()).signature(batched=False)
            )

        elif function == 'core_update':
            return SignatureDict(
                singleton=TensorSpec(type='bool', shape=()).signature(batched=False)
            )

        elif function == 'experience':
            return SignatureDict(
                timesteps=TensorSpec(type='int', shape=()).signature(batched=False),
                episodes=TensorSpec(type='int', shape=()).signature(batched=False)
            )

        elif function == 'loss':
            return SignatureDict(
                singleton=TensorSpec(type='float', shape=()).signature(batched=False)
            )

        elif function == 'update':
            return SignatureDict(
                singleton=TensorSpec(type='int', shape=()).signature(batched=False)
            )

        else:
            return super().output_signature(function=function)

    @tf_function(num_args=0, api_function=True)
    def reset(self):
        operations = list()
        zeros = tf_util.zeros(shape=(self.parallel_interactions,), dtype='int')
        operations.append(self.buffer_index.assign(value=zeros, read_value=False))
        if self.circular_buffer:
            operations.append(self.buffer_start.assign(value=zeros, read_value=False))
        operations.append(self.memory.reset())

        # TODO: Synchronization optimizer initial sync?

        with tf.control_dependencies(control_inputs=operations):
            return super().reset()

    @tf_function(num_args=6, api_function=True)
    def experience(self, *, states, internals, auxiliaries, actions, terminal, reward):
        true = tf_util.constant(value=True, dtype='bool')
        one = tf_util.constant(value=1, dtype='int')
        batch_size = tf_util.cast(x=tf.shape(input=terminal)[0], dtype='int')

        # Input assertions
        assertions = list()
        if self.config.create_tf_assertions:
            zero = tf_util.constant(value=0, dtype='int')
            assertions.extend(self.states_spec.tf_assert(
                x=states, batch_size=batch_size,
                message='Agent.experience: invalid {issue} for {name} state input.'
            ))
            assertions.extend(self.internals_spec.tf_assert(
                x=internals, batch_size=batch_size,
                message='Agent.experience: invalid {issue} for {name} internal input.'
            ))
            assertions.extend(self.auxiliaries_spec.tf_assert(
                x=auxiliaries, batch_size=batch_size,
                message='Agent.experience: invalid {issue} for {name} input.'
            ))
            assertions.extend(self.actions_spec.tf_assert(
                x=actions, batch_size=batch_size,
                message='Agent.experience: invalid {issue} for {name} action input.'
            ))
            assertions.extend(self.terminal_spec.tf_assert(
                x=terminal, batch_size=batch_size,
                message='Agent.experience: invalid {issue} for terminal input.'
            ))
            assertions.extend(self.reward_spec.tf_assert(
                x=reward, batch_size=batch_size,
                message='Agent.experience: invalid {issue} for reward input.'
            ))
            # Mask assertions
            if self.config.enable_int_action_masking:
                for name, spec in self.actions_spec.items():
                    if spec.type == 'int' and spec.num_values is not None:
                        is_valid = tf.reduce_all(input_tensor=tf.gather(
                            params=auxiliaries[name]['mask'],
                            indices=tf.expand_dims(input=actions[name], axis=(spec.rank + 1)),
                            batch_dims=(spec.rank + 1)
                        ))
                        assertions.append(tf.debugging.assert_equal(
                            x=is_valid, y=true, message="Agent.experience: invalid action / mask."
                        ))
            # Assertion: buffer indices is zero
            assertions.append(tf.debugging.assert_equal(
                x=tf.math.reduce_sum(input_tensor=self.buffer_index, axis=0), y=zero,
                message="Agent.experience: cannot be called mid-episode."
            ))
            # Assertion: one terminal
            num_terms = tf.math.count_nonzero(input=terminal, dtype=tf_util.get_dtype(type='int'))
            assertions.append(tf.debugging.assert_equal(
                x=num_terms, y=one,
                message="Agent.experience: input contains none or more than one terminal."
            ))
            # Assertion: terminal is last timestep in batch
            assertions.append(tf.debugging.assert_greater_equal(
                x=terminal[-1], y=one,
                message="Agent.experience: terminal is not the last input timestep."
            ))

        with tf.control_dependencies(control_inputs=assertions):
            # Preprocessing
            for name in states:
                if name in self.state_preprocessing:
                    states[name] = self.state_preprocessing[name].apply(
                        x=states[name], deterministic=true, independent=False
                    )
            if self.reward_preprocessing is not None:
                reward = self.reward_preprocessing.apply(
                    x=reward, deterministic=true, independent=False
                )

            # Core experience
            experienced = self.core_experience(
                states=states, internals=internals, auxiliaries=auxiliaries, actions=actions,
                terminal=terminal, reward=reward
            )

        # Increment timestep and episode
        with tf.control_dependencies(control_inputs=(experienced,)):
            assignments = list()
            assignments.append(self.timesteps.assign_add(delta=batch_size, read_value=False))
            assignments.append(self.episodes.assign_add(delta=one, read_value=False))

        with tf.control_dependencies(control_inputs=assignments):
            timestep = tf_util.identity(input=self.timesteps)
            episode = tf_util.identity(input=self.episodes)
            return timestep, episode

    @tf_function(num_args=0, api_function=True)
    def update(self):
        # Core update
        updated = self.core_update()

        with tf.control_dependencies(control_inputs=(updated,)):
            return tf_util.identity(input=self.updates)

    @tf_function(num_args=5)
    def core_act(self, *, states, internals, auxiliaries, parallel, deterministic, independent):
        zero_float = tf_util.constant(value=0.0, dtype='float')

        # On-policy policy/baseline horizon (TODO: retrieve from buffer!)
        assertions = list()
        if self.config.create_tf_assertions:
            zero = tf_util.constant(value=0, dtype='int')
            past_horizon = tf.math.maximum(
                x=self.policy.past_horizon(on_policy=True),
                y=self.baseline.past_horizon(on_policy=True)
            )
            assertions.append(tf.debugging.assert_equal(
                x=past_horizon, y=zero,
                message="Policy/baseline on-policy horizon currently not supported."
            ))
            if not independent:
                false = tf_util.constant(value=False, dtype='bool')
                assertions.append(tf.debugging.assert_equal(
                    x=deterministic, y=false,
                    message="Invalid combination deterministic and not independent."
                ))

        # Variable noise
        if len(self.policy.trainable_variables) > 0 and (
            (not independent and not self.variable_noise.is_constant(value=0.0)) or
            (independent and self.variable_noise.final_value() != 0.0)
        ):
            if independent:
                variable_noise = tf_util.constant(
                    value=self.variable_noise.final_value(), dtype=self.variable_noise.spec.type
                )
            else:
                variable_noise = self.variable_noise.value()

            def no_variable_noise():
                return [tf.zeros_like(input=var) for var in self.policy.trainable_variables]

            def apply_variable_noise():
                variable_noise_tensors = list()
                for variable in self.policy.trainable_variables:
                    noise = tf.random.normal(
                        shape=tf_util.shape(x=variable), mean=0.0, stddev=variable_noise,
                        dtype=self.variable_noise.spec.tf_type()
                    )
                    if variable.dtype != tf_util.get_dtype(type='float'):
                        noise = tf.cast(x=noise, dtype=variable.dtype)
                    assignment = variable.assign_add(delta=noise, read_value=False)
                    with tf.control_dependencies(control_inputs=(assignment,)):
                        variable_noise_tensors.append(tf_util.identity(input=noise))
                return variable_noise_tensors

            variable_noise_tensors = tf.cond(
                pred=tf.math.logical_or(
                    x=deterministic, y=tf.math.equal(x=variable_noise, y=zero_float)
                ), true_fn=no_variable_noise, false_fn=apply_variable_noise
            )

        else:
            variable_noise_tensors = list()

        with tf.control_dependencies(control_inputs=(variable_noise_tensors + assertions)):
            dependencies = list()

            # State preprocessing (after variable noise)
            for name in self.states_spec:
                if name in self.state_preprocessing:
                    states[name] = self.state_preprocessing[name].apply(
                        x=states[name], deterministic=deterministic, independent=independent
                    )

            # Policy act (after variable noise)
            batch_size = tf_util.cast(x=tf.shape(input=states.value())[0], dtype='int')
            starts = tf.range(batch_size, dtype=tf_util.get_dtype(type='int'))
            lengths = tf_util.ones(shape=(batch_size,), dtype='int')
            horizons = tf.stack(values=(starts, lengths), axis=1)
            next_internals = TensorDict()
            actions, next_internals['policy'] = self.policy.act(
                states=states, horizons=horizons, internals=internals['policy'],
                auxiliaries=auxiliaries, deterministic=deterministic, independent=independent
            )
            if isinstance(actions, tf.Tensor):
                dependencies.append(actions)
            else:
                dependencies.extend(actions.flatten())

            # Baseline internals (after variable noise)
            # TODO: shouldn't be required for independent-act
            if self.separate_baseline and len(self.internals_spec['baseline']) > 0:
                next_internals['baseline'] = self.baseline.next_internals(
                    states=states, horizons=horizons, internals=internals['baseline'],
                    actions=actions, deterministic=deterministic, independent=independent
                )
            else:
                next_internals['baseline'] = TensorDict()
            dependencies.extend(next_internals.flatten())

        # Reverse variable noise (after policy act)
        if len(variable_noise_tensors) > 0:
            with tf.control_dependencies(control_inputs=dependencies):
                dependencies = list()

                def apply_variable_noise():
                    assignments = list()
                    for var, noise in zip(self.policy.trainable_variables, variable_noise_tensors):
                        assignments.append(var.assign_sub(delta=noise, read_value=False))
                    return tf.group(*assignments)

                dependencies.append(tf.cond(
                    pred=tf.math.equal(x=variable_noise, y=zero_float),
                    true_fn=tf.no_op, false_fn=apply_variable_noise
                ))

        # Exploration
        if (not independent and (
            isinstance(self.exploration, dict) or not self.exploration.is_constant(value=0.0)
        )) or (independent and (
            isinstance(self.exploration, dict) or self.exploration.final_value() != 0.0
        )):

            # Global exploration
            if not isinstance(self.exploration, dict):
                # exploration_fns = dict()
                if not independent and not self.exploration.is_constant(value=0.0):
                    exploration = self.exploration.value()
                elif independent and self.exploration.final_value() != 0.0:
                    exploration = tf_util.constant(
                        value=self.exploration.final_value(), dtype=self.exploration.spec.type
                    )
                else:
                    assert False

            float_dtype = tf_util.get_dtype(type='float')
            for name, spec, action in self.actions_spec.zip_items(actions):

                # Per-action exploration
                if isinstance(self.exploration, dict):
                    if name not in self.exploration:
                        continue
                    elif not independent and not self.exploration[name].is_constant(value=0.0):
                        exploration = self.exploration.value()
                    elif independent and self.exploration[name].final_value() != 0.0:
                        exploration = tf_util.constant(
                            value=self.exploration[name].final_value(),
                            dtype=self.exploration[name].spec.type
                        )
                    else:
                        continue

                # Apply exploration
                if spec.type == 'bool':
                    # Bool action: if uniform[0, 1] < exploration, then uniform[True, False]

                    def apply_exploration():
                        shape = tf_util.cast(x=tf.shape(input=action), dtype='int')
                        half = tf_util.constant(value=0.5, dtype='float')
                        random_action = tf.random.uniform(shape=shape, dtype=float_dtype) < half
                        is_random = tf.random.uniform(shape=shape, dtype=float_dtype) < exploration
                        return tf.where(condition=is_random, x=random_action, y=action)

                elif spec.type == 'int' and spec.num_values is not None:
                    if self.config.enable_int_action_masking:
                        # Masked action: if uniform[0, 1] < exploration, then uniform[unmasked]
                        # (Similar code as for RandomModel.core_act)

                        def apply_exploration():
                            shape = tf_util.cast(x=tf.shape(input=action), dtype='int')
                            mask = auxiliaries[name]['mask']
                            choices = tf_util.constant(
                                value=list(range(spec.num_values)), dtype=spec.type,
                                shape=(tuple(1 for _ in spec.shape) + (1, spec.num_values))
                            )
                            one = tf_util.constant(value=1, dtype='int', shape=(1,))
                            multiples = tf.concat(values=(shape, one), axis=0)
                            choices = tf.tile(input=choices, multiples=multiples)
                            choices = tf.boolean_mask(tensor=choices, mask=mask)
                            num_valid = tf.math.count_nonzero(input=mask, axis=(spec.rank + 1))
                            num_valid = tf.reshape(tensor=num_valid, shape=(-1,))
                            masked_offset = tf.math.cumsum(x=num_valid, axis=0, exclusive=True)
                            uniform = tf.random.uniform(shape=shape, dtype=float_dtype)
                            uniform = tf.reshape(tensor=uniform, shape=(-1,))
                            num_valid = tf_util.cast(x=num_valid, dtype='float')
                            random_offset = tf.dtypes.cast(
                                x=(uniform * num_valid), dtype=tf.dtypes.int64
                            )
                            random_action = tf.gather(
                                params=choices, indices=(masked_offset + random_offset)
                            )
                            random_action = tf.reshape(tensor=random_action, shape=shape)
                            is_random = tf.random.uniform(shape=shape, dtype=float_dtype)
                            is_random = is_random < exploration
                            return tf.where(condition=is_random, x=random_action, y=action)

                    else:
                        # Int action: if uniform[0, 1] < exploration, then uniform[num_values]

                        def apply_exploration():
                            shape = tf_util.cast(x=tf.shape(input=action), dtype='int')
                            random_action = tf.random.uniform(
                                shape=shape, maxval=spec.num_values, dtype=spec.tf_type()
                            )
                            is_random = tf.random.uniform(shape=shape, dtype=float_dtype)
                            is_random = is_random < exploration
                            return tf.where(condition=is_random, x=random_action, y=action)

                else:
                    # Int/float action: action + normal[0, exploration]

                    def apply_exploration():
                        shape = tf_util.cast(x=tf.shape(input=action), dtype='int')
                        noise = tf.random.normal(shape=shape, dtype=spec.tf_type())
                        x = action + noise * exploration

                        # Clip action if left-/right-bounded
                        if spec.min_value is not None:
                            x = tf.math.maximum(x=x, y=spec.min_value)
                        if spec.max_value is not None:
                            x = tf.math.minimum(x=x, y=spec.max_value)
                        return x

                # if isinstance(self.exploration, dict):
                # Per-action exploration
                actions[name] = tf.cond(
                    pred=tf.math.logical_or(
                        x=deterministic, y=tf.math.equal(x=exploration, y=zero_float)
                    ), true_fn=(lambda: action), false_fn=apply_exploration
                )

                # else:
                #     exploration_fns[name] = apply_exploration

            # if not isinstance(self.exploration, dict):
            #     # Global exploration

            #     def apply_exploration():
            #         for name in self.actions_spec:
            #             actions[name] = exploration_fns[name]()
            #         return actions

            #     actions = tf.cond(
            #         pred=tf.math.equal(x=exploration, y=zero_float),
            #         true_fn=(lambda: actions), false_fn=apply_exploration
            #     )

        # Update states/internals/auxiliaries/actions buffers
        if not independent:
            assignments = list()
            buffer_index = tf.gather(params=self.buffer_index, indices=parallel)
            if self.circular_buffer:
                buffer_index = tf.math.mod(x=buffer_index, y=self.buffer_capacity)
            indices = tf.stack(values=(parallel, buffer_index), axis=1)
            for name, buffer, state in self.states_buffer.zip_items(states):
                value = tf.tensor_scatter_nd_update(tensor=buffer, indices=indices, updates=state)
                assignments.append(buffer.assign(value=value))
                # assignments.append(buffer.scatter_nd_update(indices=indices, updates=state))
            for name, buffer, internal in self.internals_buffer.zip_items(internals):  # not next_*
                value = tf.tensor_scatter_nd_update(
                    tensor=buffer, indices=indices, updates=internal
                )
                assignments.append(buffer.assign(value=value))
                # assignments.append(buffer.scatter_nd_update(indices=indices, updates=internal))
            for name, buffer, auxiliary in self.auxiliaries_buffer.zip_items(auxiliaries):
                value = tf.tensor_scatter_nd_update(
                    tensor=buffer, indices=indices, updates=auxiliary
                )
                assignments.append(buffer.assign(value=value))
                # assignments.append(buffer.scatter_nd_update(indices=indices, updates=auxiliary))
            for name, buffer, action in self.actions_buffer.zip_items(actions):
                value = tf.tensor_scatter_nd_update(tensor=buffer, indices=indices, updates=action)
                assignments.append(buffer.assign(value=value))
                # assignments.append(buffer.scatter_nd_update(indices=indices, updates=action))

            # Increment buffer index (after buffer assignments)
            with tf.control_dependencies(control_inputs=assignments):
                ones = tf_util.ones(shape=(batch_size,), dtype='int')
                indices = tf.expand_dims(input=parallel, axis=1)
                value = tf.tensor_scatter_nd_add(
                    tensor=self.buffer_index, indices=indices, updates=ones
                )
                dependencies.append(self.buffer_index.assign(value=value))
                # sparse_delta = tf.IndexedSlices(values=ones, indices=parallel)
                # dependencies.append(self.buffer_index.scatter_add(sparse_delta=sparse_delta))

        with tf.control_dependencies(control_inputs=dependencies):
            actions = actions.fmap(
                function=(lambda name, x: tf_util.identity(input=x, name=name)), with_names=True
            )
            next_internals = next_internals.fmap(
                function=(lambda name, x: tf_util.identity(input=x, name=name)), with_names=True
            )
            return actions, next_internals

    @tf_function(num_args=3)
    def core_observe(self, *, terminal, reward, parallel):
        zero = tf_util.constant(value=0, dtype='int')
        one = tf_util.constant(value=1, dtype='int')
        buffer_index = tf.gather(params=self.buffer_index, indices=parallel)
        batch_size = tf_util.cast(x=tf.shape(input=terminal)[0], dtype='int')
        expanded_parallel = tf.expand_dims(input=tf.expand_dims(input=parallel, axis=0), axis=1)
        if self.circular_buffer:
            buffer_start = tf.gather(params=self.buffer_start, indices=parallel)

        # Assertion: size of terminal equals number of buffered timesteps
        assertions = list()
        # if self.config.create_tf_assertions:
        #     if self.circular_buffer:
        #         maybe_one = tf.minimum(x=buffer_index, y=self.reward_horizon.value())
        #         assertions.append(tf.debugging.assert_equal(
        #             x=batch_size, y=(buffer_index - buffer_start - maybe_one),
        #             message="Agent.observe: number of observe-timesteps has to be equal to number "
        #                     "of buffered act-timesteps."
        #         ))
        #     else:
        #         assertions.append(tf.debugging.assert_equal(
        #             x=batch_size, y=buffer_index,
        #             message="Agent.observe: number of observe-timesteps has to be equal to number "
        #                     "of buffered act-timesteps."
        #         ))

        if self.config.buffer_observe == 'episode':
            # Observe inputs are always buffered in agent until episode is terminated
            # --> Call core_experience directly, no need for terminal/reward buffers

            def fn_nonterminal():
                # Should not be called
                return tf.debugging.assert_equal(x=batch_size, y=zero)

            def fn_terminal():
                # Gather values from buffers, and episode experience
                function = (lambda x: x[parallel, :buffer_index])
                states = self.states_buffer.fmap(function=function, cls=TensorDict)
                internals = self.internals_buffer.fmap(function=function, cls=TensorDict)
                auxiliaries = self.auxiliaries_buffer.fmap(function=function, cls=TensorDict)
                actions = self.actions_buffer.fmap(function=function, cls=TensorDict)
                return self.core_experience(
                    states=states, internals=internals, auxiliaries=auxiliaries, actions=actions,
                    terminal=terminal, reward=reward
                )

        elif self.reward_horizon == 'episode' or self.parallel_interactions > 1:
            # Observe inputs need to be buffered until episode is terminated
            # --> Call core_experience if terminal, otherwise buffer terminal/reward
            batch_parallel = tf.fill(dims=(batch_size,), value=parallel)

            def fn_nonterminal():
                # Update terminal/reward buffers
                assignments = list()
                indices = tf.range(start=(buffer_index - batch_size), limit=buffer_index)
                indices = tf.stack(values=(batch_parallel, indices), axis=1)
                value = tf.tensor_scatter_nd_update(
                    tensor=self.terminal_buffer, indices=indices, updates=terminal
                )
                assignments.append(self.terminal_buffer.assign(value=value))
                value = tf.tensor_scatter_nd_update(
                    tensor=self.reward_buffer, indices=indices, updates=reward
                )
                assignments.append(self.reward_buffer.assign(value=value))
                return tf.group(assignments)

            def fn_terminal():
                # Gather values from buffers, and episode experience
                function = (lambda x: x[parallel, :buffer_index])
                states = self.states_buffer.fmap(function=function, cls=TensorDict)
                internals = self.internals_buffer.fmap(function=function, cls=TensorDict)
                auxiliaries = self.auxiliaries_buffer.fmap(function=function, cls=TensorDict)
                actions = self.actions_buffer.fmap(function=function, cls=TensorDict)
                episode_terminal = self.terminal_buffer[parallel, :buffer_index - batch_size]
                episode_reward = self.reward_buffer[parallel, :buffer_index - batch_size]
                episode_terminal = tf.concat(values=(episode_terminal, terminal), axis=0)
                episode_reward = tf.concat(values=(episode_reward, reward), axis=0)
                return self.core_experience(
                    states=states, internals=internals, auxiliaries=auxiliaries, actions=actions,
                    terminal=episode_terminal, reward=episode_reward
                )

        else:
            # Observe inputs are buffered temporarily and return is computed as soon as possible
            # --> Call core_experience if terminal, otherwise ???
            capacity = tf_util.constant(value=self.buffer_capacity, dtype='int')
            reward_horizon = self.reward_horizon.value()
            reward_discount = self.reward_discount.value()
            batch_parallel = tf.fill(dims=(batch_size,), value=parallel)

            def fn_nonterminal():
                # Update terminal/reward buffers
                assignments = list()
                indices = tf.range(start=(buffer_index - batch_size), limit=buffer_index)
                indices = tf.math.mod(x=indices, y=capacity)
                indices = tf.stack(values=(batch_parallel, indices), axis=1)
                value = tf.tensor_scatter_nd_update(
                    tensor=self.terminal_buffer, indices=indices, updates=terminal
                )
                assignments.append(self.terminal_buffer.assign(value=value))
                value = tf.tensor_scatter_nd_update(
                    tensor=self.reward_buffer, indices=indices, updates=reward
                )
                assignments.append(self.reward_buffer.assign(value=value))
                with tf.control_dependencies(control_inputs=assignments):
                    # Number of completed timesteps to process
                    num_complete = buffer_index - buffer_start - reward_horizon

                    def true_fn():
                        return self._nonterminal_experience(
                            parallel=parallel, buffer_start=buffer_start, buffer_index=buffer_index,
                            reward_horizon=reward_horizon, num_complete=num_complete,
                            reward_discount=reward_discount
                        )

                    return tf.cond(pred=(num_complete > zero), true_fn=true_fn, false_fn=tf.no_op)

            def fn_terminal():
                # Gather values from buffers
                indices = tf.range(start=buffer_start, limit=buffer_index)
                indices = tf.math.mod(x=indices, y=capacity)
                function = (lambda x: tf.gather(params=x[parallel], indices=indices))
                states = self.states_buffer.fmap(function=function, cls=TensorDict)
                internals = self.internals_buffer.fmap(function=function, cls=TensorDict)
                auxiliaries = self.auxiliaries_buffer.fmap(function=function, cls=TensorDict)
                actions = self.actions_buffer.fmap(function=function, cls=TensorDict)
                indices = tf.range(buffer_start, buffer_index - batch_size)
                indices = tf.math.mod(x=indices, y=capacity)
                episode_terminal = tf.gather(params=self.terminal_buffer[parallel], indices=indices)
                episode_reward = tf.gather(params=self.reward_buffer[parallel], indices=indices)
                episode_terminal = tf.concat(values=(episode_terminal, terminal), axis=0)
                episode_reward = tf.concat(values=(episode_reward, reward), axis=0)

                # Episode experience
                experienced = self.core_experience(
                    states=states, internals=internals, auxiliaries=auxiliaries, actions=actions,
                    terminal=episode_terminal, reward=episode_reward
                )

                # Increment buffer start index
                with tf.control_dependencies(control_inputs=(indices,)):
                    zeros = tf_util.zeros(shape=(1,), dtype='int')
                    value = tf.tensor_scatter_nd_update(
                        tensor=self.buffer_start, indices=expanded_parallel, updates=zeros
                    )
                    assignment = self.buffer_start.assign(value=value)
                    # sparse_delta = tf.IndexedSlices(values=zero, indices=parallel)
                    # assignment = self.buffer_start.scatter_update(sparse_delta=sparse_delta)

                return tf.group((experienced, assignment))

        def fn_terminal_continuation():
            # Appropriate terminal function above
            operations = [fn_terminal()]

            # Reset buffer index
            with tf.control_dependencies(control_inputs=operations):
                updates = tf_util.zeros(shape=(1,), dtype='int')
                indices = tf.expand_dims(input=tf.expand_dims(input=parallel, axis=0), axis=1)
                value = tf.tensor_scatter_nd_update(
                    tensor=self.buffer_index, indices=indices, updates=updates
                )
                operations.append(self.buffer_index.assign(value=value))
                # sparse_delta = tf.IndexedSlices(values=zero, indices=parallel)
                # operations.append(self.buffer_index.scatter_update(sparse_delta=sparse_delta))

            # Preprocessed episode reward summaries (before preprocessed episode reward reset)
            if self.reward_preprocessing is not None:
                dependencies = list()
                if self.summaries == 'all' or 'reward' in self.summaries or \
                        self.tracking == 'all' or 'reward' in self.tracking:
                    if self.summaries == 'all' or 'reward' in self.summaries:
                        summarizer = self.summarizer.as_default()
                        summarizer.__enter__()
                    else:
                        summarizer = None
                    x = tf.gather(params=self.preprocessed_episode_return, indices=parallel)
                    if summarizer is not None:
                        dependencies.append(tf.summary.scalar(
                            name='preprocessed-episode-return', data=x, step=self.episodes
                        ))
                    dependencies.extend(self.track(
                        label='reward', name='preprocessed-episode-return', data=x
                    ))
                    if summarizer is not None:
                        summarizer.__exit__(None, None, None)

                # Reset preprocessed episode reward
                with tf.control_dependencies(control_inputs=dependencies):
                    zeros = tf_util.zeros(shape=(1,), dtype='float')
                    value = tf.tensor_scatter_nd_update(
                        tensor=self.preprocessed_episode_return, indices=expanded_parallel,
                        updates=zeros
                    )
                    operations.append(self.preprocessed_episode_return.assign(value=value))
                    # zero_float = tf_util.constant(value=0.0, dtype='float')
                    # sparse_delta = tf.IndexedSlices(values=zero_float, indices=parallel)
                    # operations.append(
                    #     self.preprocessed_episode_return.scatter_update(sparse_delta=sparse_delta)
                    # )

            # Reset preprocessors
            for preprocessor in self.state_preprocessing.values():
                operations.append(preprocessor.reset())
            if self.reward_preprocessing is not None:
                operations.append(self.reward_preprocessing.reset())

            return tf.group(*operations)

        # Reward preprocessing
        dependencies = assertions
        if self.reward_preprocessing is not None:
            with tf.control_dependencies(control_inputs=dependencies):
                dependencies = list()
                true = tf_util.constant(value=True, dtype='bool')
                reward = self.reward_preprocessing.apply(
                    x=reward, deterministic=true, independent=False
                )

                # Preprocessed reward summary
                if self.summaries == 'all' or 'reward' in self.summaries or \
                        self.tracking == 'all' or 'reward' in self.tracking:
                    if self.summaries == 'all' or 'reward' in self.summaries:
                        summarizer = self.summarizer.as_default()
                        summarizer.__enter__()
                    else:
                        summarizer = None
                    x = tf.math.reduce_mean(input_tensor=reward, axis=0)
                    if summarizer is not None:
                        dependencies.append(tf.summary.scalar(
                            name='preprocessed-reward', data=x, step=self.timesteps
                        ))
                    dependencies.extend(self.track(
                        label='reward', name='preprocessed-reward', data=x
                    ))
                    if summarizer is not None:
                        summarizer.__exit__(None, None, None)

                # Update preprocessed episode reward
                sum_reward = tf.math.reduce_sum(input_tensor=reward, keepdims=True)
                value = tf.tensor_scatter_nd_add(
                    tensor=self.preprocessed_episode_return, indices=expanded_parallel,
                    updates=sum_reward
                )
                dependencies.append(self.preprocessed_episode_return.assign(value=value))
                # sum_reward = tf.math.reduce_sum(input_tensor=reward)
                # sparse_delta = tf.IndexedSlices(values=sum_reward, indices=parallel)
                # dependencies.append(
                #     self.preprocessed_episode_return.scatter_add(sparse_delta=sparse_delta)
                # )

        # Handle terminal vs non-terminal (after preprocessed episode reward)
        with tf.control_dependencies(control_inputs=dependencies):
            is_terminal = tf.concat(values=([zero], terminal), axis=0)[-1] > zero
            experienced = tf.cond(
                pred=is_terminal, true_fn=fn_terminal_continuation, false_fn=fn_nonterminal
            )

        # Handle periodic update
        with tf.control_dependencies(control_inputs=(experienced,)):
            if self.update_frequency is None:
                updated = tf_util.constant(value=False, dtype='bool')

            else:
                frequency = self.update_frequency.value()
                start = self.update_start.value()

                if self.update_unit == 'timesteps':
                    # Timestep-based batch
                    past_horizon = tf.math.maximum(
                        x=self.policy.past_horizon(on_policy=False),
                        y=self.baseline.past_horizon(on_policy=False)
                    )
                    unit = self.timesteps
                    start = tf.math.maximum(x=start, y=(frequency + past_horizon + one))
                    if self.reward_horizon == 'episode':
                        min_start = tf.where(
                            condition=(self.episodes > zero), x=start, y=(unit + one)
                        )
                        start = tf.math.maximum(x=start, y=min_start)
                    else:
                        start += self.reward_horizon.value()
                    if self.config.buffer_observe == 'episode':
                        min_start = tf.where(
                            condition=(self.episodes > zero), x=start, y=(unit + one)
                        )
                        start = tf.math.maximum(x=start, y=min_start)
                    else:
                        buffer_observe = tf_util.constant(
                            value=self.config.buffer_observe, dtype='int'
                        )
                        start = tf.math.maximum(x=start, y=buffer_observe)

                elif self.update_unit == 'episodes':
                    # Episode-based batch
                    start = tf.math.maximum(x=start, y=frequency)
                    # (Episode counter is only incremented at the end of observe)
                    unit = self.episodes + tf.where(condition=is_terminal, x=one, y=zero)

                unit = unit - start
                is_frequency = tf.math.greater_equal(x=unit, y=(self.last_update + frequency))

                def perform_update():
                    assignment = self.last_update.assign(value=unit, read_value=False)
                    with tf.control_dependencies(control_inputs=(assignment,)):
                        return self.core_update()

                def no_update():
                    return tf_util.constant(value=False, dtype='bool')

                updated = tf.cond(pred=is_frequency, true_fn=perform_update, false_fn=no_update)

        with tf.control_dependencies(control_inputs=(updated,)):
            return tf_util.identity(input=updated)

    def _nonterminal_experience(
        self, *, parallel, buffer_start, buffer_index, reward_horizon, num_complete, reward_discount
    ):
        # (similar to _terminal_experience_parallel)
        one = tf_util.constant(value=1, dtype='int')
        capacity = tf_util.constant(value=self.buffer_capacity, dtype='int')

        # Whether to predict horizon values now
        if self.predict_horizon_values != 'early':
            assert self.trace_decay.is_constant(value=1.0)
            horizon_values = tf_util.zeros(shape=(num_complete,), dtype='float')

        else:
            # Baseline horizon
            baseline_horizon = self.baseline.past_horizon(on_policy=True)
            if self.trace_decay.is_constant(value=1.0):
                assertion = tf.debugging.assert_less_equal(
                    x=baseline_horizon, y=reward_horizon,
                    message="Baseline on-policy horizon greater than reward estimation horizon "
                            "currently not supported if prediction_horizon_values = \"early\"."
                )
            else:
                zero = tf_util.constant(value=0, dtype='int')
                assertion = tf.debugging.assert_less_equal(
                    x=baseline_horizon, y=zero,
                    message="Baseline on-policy horizon currently not supported if "
                            "trace_decay != 1.0."
                )

            with tf.control_dependencies(control_inputs=(assertion,)):

                # Index range to gather from buffers
                if self.trace_decay.is_constant(value=1.0):
                    # Only indices relevant for horizon values
                    indices = tf.range(
                        start=(buffer_start + reward_horizon - baseline_horizon), limit=buffer_index
                    )
                    ints_end = num_complete
                    auxs_start = baseline_horizon
                    horizons_start = tf.range(num_complete)
                    horizons_length = tf.fill(dims=(num_complete,), value=(baseline_horizon + one))
                else:
                    # All indices
                    indices = tf.range(start=(buffer_start + one), limit=buffer_index)
                    ints_end = None
                    auxs_start = None
                    horizons_start = tf.range(buffer_index - buffer_start - one)
                    horizons_length = tf.ones_like(input=horizons_start)
                indices = tf.math.mod(x=indices, y=capacity)

                # Return-sequence per timestep, as horizons indexing tensor
                horizons = tf.stack(values=(horizons_start, horizons_length), axis=1)

                # Gather states
                function = (lambda x: tf.gather(params=x[parallel], indices=indices))
                states = self.states_buffer.fmap(function=function, cls=TensorDict)

                # Gather internals, only for return-sequence start
                function = (lambda x: tf.gather(params=x[parallel], indices=indices[:ints_end]))
                key = ('baseline' if self.separate_baseline else 'policy')
                if len(self.internals_spec[key]) > 0:
                    internals = self.internals_buffer[key].fmap(function=function, cls=TensorDict)
                else:
                    internals = TensorDict()

                # Gather auxiliaries (and actions), only for return-sequence end
                function = (lambda x: tf.gather(params=x[parallel], indices=indices[auxs_start:]))
                auxiliaries = self.auxiliaries_buffer.fmap(function=function, cls=TensorDict)

                # Predict values
                if self.predict_action_values:
                    # TODO: option to re-sample action deterministically?
                    actions = self.actions_buffer.fmap(function=function, cls=TensorDict)
                    values = self.baseline.action_value(
                        states=states, horizons=horizons, internals=internals,
                        auxiliaries=auxiliaries, actions=actions
                    )
                else:
                    values = self.baseline.state_value(
                        states=states, horizons=horizons, internals=internals,
                        auxiliaries=auxiliaries
                    )

                # Horizon values
                if self.trace_decay.is_constant(value=1.0):
                    horizon_values = values
                else:
                    horizon_values = values[reward_horizon - one:]

        # Gather all rewards (incl return-horizon) from buffer
        indices = tf.range(start=buffer_start, limit=(buffer_index - one))
        indices = tf.math.mod(x=indices, y=capacity)
        reward = tf.gather(params=self.reward_buffer[parallel], indices=indices)

        # Recursive return
        if self.trace_decay.is_constant(value=1.0):
            # Discounted cumulative sum
            def recursive_return(next_return, index):
                return reward[index: index + num_complete] + reward_discount * next_return

        else:
            # TD-lambda
            one_float = tf_util.constant(value=1.0, dtype='float')
            trace_decay = self.trace_decay.value()

            def recursive_return(next_return, index):
                next_value = values[index: index + num_complete]
                next_return = (one_float - trace_decay) * next_value + trace_decay * next_return
                return reward[index: index + num_complete] + reward_discount * next_return

        reward = tf.foldr(
            fn=recursive_return, elems=tf.range(reward_horizon), initializer=horizon_values
        )

        # Gather other values of completed timesteps from buffers
        indices = tf.range(start=buffer_start, limit=(buffer_start + num_complete))
        indices = tf.math.mod(x=indices, y=capacity)
        function = (lambda x: tf.gather(params=x[parallel], indices=indices))
        states = self.states_buffer.fmap(function=function, cls=TensorDict)
        internals = self.internals_buffer.fmap(function=function, cls=TensorDict)
        auxiliaries = self.auxiliaries_buffer.fmap(function=function, cls=TensorDict)
        actions = self.actions_buffer.fmap(function=function, cls=TensorDict)
        terminal = function(self.terminal_buffer)

        # Store completed timesteps
        experienced = self.memory.enqueue(
            states=states, internals=internals, auxiliaries=auxiliaries, actions=actions,
            terminal=terminal, reward=reward
        )

        # Increment buffer start index
        with tf.control_dependencies(control_inputs=(indices,)):
            updates = tf.expand_dims(input=num_complete, axis=0)
            indices = tf.expand_dims(input=tf.expand_dims(input=parallel, axis=0), axis=1)
            value = tf.tensor_scatter_nd_add(
                tensor=self.buffer_start, indices=indices, updates=updates
            )
            assignment = self.buffer_start.assign(value=value)
            # sparse_delta = tf.IndexedSlices(values=num_complete, indices=parallel)
            # assignment = self.buffer_start.scatter_add(sparse_delta=sparse_delta)

        return tf.group((experienced, assignment))

    @tf_function(num_args=6)
    def core_experience(self, *, states, internals, auxiliaries, actions, terminal, reward):
        episode_length = tf_util.cast(x=tf.shape(input=terminal)[0], dtype='int')
        reward_discount = self.reward_discount.value()

        if self.reward_horizon == 'episode':
            # Reward horizon is entire episode
            reward = self._terminal_experience_iterative(
                episode_length=episode_length, reward_discount=reward_discount, states=states,
                internals=internals, auxiliaries=auxiliaries, actions=actions, reward=reward,
                terminal=terminal
            )

        else:
            # Optimize required loop iterations, so whether to process remaining timesteps
            #     - iteratively, if remaining episode length is at most reward horizon
            #     - in parallel, if reward horizon is less than remaining episode length
            reward_horizon = self.reward_horizon.value()

            def true_fn():
                return self._terminal_experience_iterative(
                    episode_length=episode_length,  reward_discount=reward_discount, states=states,
                    internals=internals, auxiliaries=auxiliaries, actions=actions, reward=reward,
                    terminal=terminal
                )

            def false_fn():
                return self._terminal_experience_parallel(
                    episode_length=episode_length, reward_horizon=reward_horizon,
                    reward_discount=reward_discount, states=states, internals=internals,
                    auxiliaries=auxiliaries, actions=actions, reward=reward, terminal=terminal
                )

            reward = tf.cond(
                pred=(episode_length <= reward_horizon), true_fn=true_fn, false_fn=false_fn
            )

        # Store episode
        return self.memory.enqueue(
            states=states, internals=internals, auxiliaries=auxiliaries, actions=actions,
            terminal=terminal, reward=reward
        )

    def _terminal_experience_iterative(
        self, *, episode_length, reward_discount,
        states, internals, auxiliaries, actions, reward, terminal
    ):
        zero = tf_util.constant(value=0, dtype='int')
        one = tf_util.constant(value=1, dtype='int')
        zero_float = tf_util.constant(value=0.0, dtype='float')
        internals = (internals['baseline'] if self.separate_baseline else internals['policy'])

        if self.trace_decay.is_constant(value=1.0):
            # Whether to predict horizon/terminal values now
            if self.predict_horizon_values != 'early':

                # Whether to predict all or only abort-terminals
                # (-reward[-1] since terminal state value will be predicted)
                terminal_value = -reward[-1] / reward_discount
                if not self.predict_terminal_values:
                    is_terminal = tf.math.equal(x=terminal[-1], y=one)
                    terminal_value = tf.where(condition=is_terminal, x=zero_float, y=terminal_value)

            else:

                def predict_terminal_value():
                    # Baseline horizon
                    baseline_horizon = self.baseline.past_horizon(on_policy=True)
                    baseline_horizon = tf.math.minimum(x=baseline_horizon, y=episode_length)

                    # Single-step horizon
                    horizon_start = episode_length - one - baseline_horizon
                    horizons = tf.expand_dims(
                        input=tf.stack(values=(zero, baseline_horizon + one)), axis=0
                    )

                    # Predict values
                    if self.predict_action_values:
                        # TODO: option to re-sample action deterministically?
                        # Use given actions since early estimate
                        # if self.separate_baseline:
                        #     policy_horizon = self.policy.past_horizon(on_policy=True)
                        #     policy_horizon = tf.math.minimum(x=policy_horizon, y=episode_length)
                        #     policy_horizon_start = terminal_index - policy_horizon
                        # else:
                        #     policy_horizon_start = past_horizon_start
                        # deterministic = tf_util.constant(value=True, dtype='bool')
                        # _actions, _ = self.policy.act(
                        #     states=states[policy_horizon_start:], horizons=horizons[:maybe_one],
                        #     internals=internals['policy'][policy_horizon_start: policy_horizon_start + maybe_one],
                        #     auxiliaries=auxiliaries[terminal_index:], deterministic=deterministic,
                        #     independent=True
                        # )
                        terminal_value = self.baseline.action_value(
                            states=states[horizon_start:], horizons=horizons,
                            internals=internals[horizon_start: horizon_start + one],
                            auxiliaries=auxiliaries[-1:],
                            actions=actions[-1:]
                        )
                    else:
                        terminal_value = self.baseline.state_value(
                            states=states[horizon_start:], horizons=horizons,
                            internals=internals[horizon_start: horizon_start + one],
                            auxiliaries=auxiliaries[-1:]
                        )

                    # Modification to correct for use as initializer in tf.scan
                    # (-reward[-1] since terminal state value will be predicted)
                    return (terminal_value[0] - reward[-1]) / reward_discount

                # Whether to predict all or only abort-terminals
                if self.predict_terminal_values:
                    terminal_value = predict_terminal_value()
                else:
                    is_terminal = tf.math.equal(x=terminal[-1], y=one)
                    terminal_value = tf.cond(
                        pred=is_terminal, true_fn=(lambda: zero_float),
                        false_fn=predict_terminal_value
                    )

            # Discounted cumulative sum return
            def recursive_return(next_return, current_reward):
                return current_reward + reward_discount * next_return

            return tf.scan(
                fn=recursive_return, elems=reward, initializer=terminal_value, reverse=True
            )

        else:
            # Baseline horizon
            baseline_horizon = self.baseline.past_horizon(on_policy=True)
            assertion = tf.debugging.assert_equal(
                x=baseline_horizon, y=zero,
                message="Baseline cannot have on-policy horizon if trace_decay != 1.0."
            )

            with tf.control_dependencies(control_inputs=(assertion,)):
                # Baseline-horizon-sequence per timestep, as horizons indexing tensor
                horizons_start = tf.range(episode_length - one)
                horizons_length = tf.fill(dims=(episode_length - one,), value=one)
                horizons = tf.stack(values=(horizons_start, horizons_length), axis=1)

                if self.predict_action_values:
                    # TODO: option to re-sample action deterministically?
                    values = self.baseline.action_value(
                        states=states[1:], horizons=horizons, internals=internals[1:],
                        auxiliaries=auxiliaries[1:], actions=actions[1:]
                    )
                else:
                    values = self.baseline.state_value(
                        states=states[1:], horizons=horizons, internals=internals[1:],
                        auxiliaries=auxiliaries[1:]
                    )

                # Modification to correct for use as initializer in tf.scan
                # (-reward[-1] since terminal state value will be predicted)
                terminal_value = (values[-1] - reward[-1]) / reward_discount

                # Whether to predict all or only abort-terminals
                if not self.predict_terminal_values:
                    is_terminal = tf.math.equal(x=terminal[-1], y=one)
                    terminal_value = tf.where(condition=is_terminal, x=zero_float, y=terminal_value)

                values = tf.concat(values=(values, [terminal_value]), axis=0)

                # TD-lambda return
                one_float = tf_util.constant(value=1.0, dtype='float')
                trace_decay = self.trace_decay.value()

                def recursive_return(next_return, reward_value):
                    current_reward, next_value = reward_value
                    next_return = (one_float - trace_decay) * next_value + trace_decay * next_return
                    return current_reward + reward_discount * next_return

                return tf.scan(
                    fn=recursive_return, elems=(reward, values), initializer=terminal_value,
                    reverse=True
                )

    def _terminal_experience_parallel(
        self, *, episode_length, reward_horizon, reward_discount,
        states, internals, auxiliaries, actions, reward, terminal
    ):
        # (similar to _nonterminal_experience)
        one = tf_util.constant(value=1, dtype='int')
        internals = (internals['baseline'] if self.separate_baseline else internals['policy'])

        # Whether to predict horizon values now
        if self.predict_horizon_values != 'early':
            assert self.trace_decay.is_constant(value=1.0)

            # Whether to predict all or only abort-terminals
            terminal_value = tf_util.constant(value=0.0, dtype='float')
            if not self.predict_terminal_values:
                is_terminal = tf.math.equal(x=terminal[-1], y=one)
                terminal_value = tf.where(condition=is_terminal, x=reward[-1], y=terminal_value)

            # Horizon-expanded rewards and values
            horizon_values = tf_util.zeros(shape=(episode_length,), dtype='float')
            reward = tf.concat(
                values=(reward[:-1], [terminal_value], horizon_values[:reward_horizon]), axis=0
            )

        else:
            # Baseline horizon
            baseline_horizon = self.baseline.past_horizon(on_policy=True)
            assertions = list()  # (control dependency below, before baseline call)
            if not self.trace_decay.is_constant(value=1.0):
                zero = tf_util.constant(value=0, dtype='int')
                assertions.append(tf.debugging.assert_equal(
                    x=baseline_horizon, y=zero,
                    message="Baseline cannot have on-policy horizon if trace_decay != 1.0."
                ))

            # Index starts/ends
            if self.trace_decay.is_constant(value=1.0):
                # Only indices relevant for horizon values
                reward_horizon_start = reward_horizon
                zero = tf_util.constant(value=0, dtype='int')
                baseline_horizon_start = tf.maximum(
                    x=(reward_horizon_start - baseline_horizon), y=zero
                )
                baseline_horizon_end = episode_length - baseline_horizon
                baseline_horizon_end = tf.maximum(x=baseline_horizon_end, y=baseline_horizon_start)
                horizons_start = tf.range(baseline_horizon_end - baseline_horizon_start)
                horizons_length = reward_horizon_start + horizons_start
                horizons_length = tf.math.minimum(x=horizons_length, y=(baseline_horizon + one))
            else:
                # All indices
                reward_horizon_start = 1
                baseline_horizon_start = 1
                baseline_horizon_end = None
                horizons_start = tf.range(episode_length - one)
                horizons_length = tf.ones_like(input=horizons_start)

            # Baseline-horizon-sequence per timestep, as horizons indexing tensor
            horizons = tf.stack(values=(horizons_start, horizons_length), axis=1)

            # Predict values
            with tf.control_dependencies(control_inputs=assertions):
                if self.predict_action_values:
                    # TODO: option to re-sample action deterministically?
                    values = self.baseline.action_value(
                        states=states[baseline_horizon_start:],
                        horizons=horizons,
                        internals=internals[baseline_horizon_start: baseline_horizon_end],
                        auxiliaries=auxiliaries[reward_horizon_start:],
                        actions=actions[reward_horizon_start:]
                    )
                else:
                    values = self.baseline.state_value(
                        states=states[baseline_horizon_start:],
                        horizons=horizons,
                        internals=internals[baseline_horizon_start: baseline_horizon_end],
                        auxiliaries=auxiliaries[reward_horizon_start:]
                    )

            # Whether to predict all or only abort-terminals
            terminal_value = values[-1]
            if not self.predict_terminal_values:
                is_terminal = tf.math.equal(x=terminal[-1], y=one)
                terminal_value = tf.where(condition=is_terminal, x=reward[-1], y=terminal_value)

            # Horizon-expanded rewards and values
            zeros_reward_horizon = tf_util.zeros(shape=(reward_horizon - one,), dtype='float')
            reward = tf.concat(values=(reward[:-1], [terminal_value], zeros_reward_horizon), axis=0)
            zeros_reward_horizon = tf_util.zeros(shape=(reward_horizon,), dtype='float')
            values = tf.concat(values=(values, zeros_reward_horizon), axis=0)

            # Horizon values
            if self.trace_decay.is_constant(value=1.0):
                horizon_values = values
            else:
                horizon_values = values[reward_horizon - one:]

        # Recursive return
        if self.trace_decay.is_constant(value=1.0):
            # Discounted cumulative sum
            def recursive_return(next_return, index):
                return reward[index: index + episode_length] + reward_discount * next_return

        else:
            # TD-lambda
            one_float = tf_util.constant(value=1.0, dtype='float')
            trace_decay = self.trace_decay.value()

            def recursive_return(next_return, index):
                next_value = values[index: index + episode_length]
                next_return = (one_float - trace_decay) * next_value + trace_decay * next_return
                return reward[index: index + episode_length] + reward_discount * next_return

        return tf.foldr(
            fn=recursive_return, elems=tf.range(reward_horizon), initializer=horizon_values
        )

    @tf_function(num_args=0)
    def core_update(self):
        zero = tf_util.constant(value=0, dtype='int')
        one = tf_util.constant(value=1, dtype='int')
        true = tf_util.constant(value=True, dtype='bool')

        # Retrieve batch
        batch_size = self.update_batch_size.value()
        if self.update_unit == 'timesteps':
            # Timestep-based batch
            # Dependency horizon
            past_horizon = tf.math.maximum(
                x=self.policy.past_horizon(on_policy=False),
                y=self.baseline.past_horizon(on_policy=False)
            )
            if self.predict_horizon_values != 'late':
                future_horizon = zero
            elif self.reward_horizon == 'episode':
                future_horizon = tf_util.constant(value=self.max_episode_timesteps, dtype='int')
            else:
                future_horizon = self.reward_horizon.value()
            indices = self.memory.retrieve_timesteps(
                n=batch_size, past_horizon=past_horizon, future_horizon=future_horizon
            )
        elif self.update_unit == 'episodes':
            # Episode-based batch
            indices = self.memory.retrieve_episodes(n=batch_size)

        # Retrieve states and internals
        policy_horizon = self.policy.past_horizon(on_policy=False)
        if self.separate_baseline and self.baseline_optimizer is None:
            assertions = list()
            if self.config.create_tf_assertions:
                assertions.append(tf.debugging.assert_equal(
                    x=policy_horizon, y=self.baseline.past_horizon(on_policy=False),
                    message="Policy and baseline cannot depend on a different number of previous "
                            "states if baseline_optimizer is None."
                ))
            with tf.control_dependencies(control_inputs=assertions):
                policy_horizons, sequence_values, initial_values = self.memory.predecessors(
                    indices=indices, horizon=policy_horizon, sequence_values=('states',),
                    initial_values=('internals',)
                )
                baseline_horizons = policy_horizons
                baseline_states = policy_states = sequence_values['states']
                internals = policy_internals = initial_values['internals']
                if self.separate_baseline:
                    baseline_internals = policy_internals['baseline']
                else:
                    baseline_internals = policy_internals
        else:
            if self.baseline_optimizer is None:
                policy_horizons, sequence_values, initial_values = self.memory.predecessors(
                    indices=indices, horizon=policy_horizon, sequence_values=('states',),
                    initial_values=('internals',)
                )
                policy_states = sequence_values['states']
                internals = policy_internals = initial_values['internals']
            elif len(self.internals_spec['policy']) > 0:
                policy_horizons, sequence_values, initial_values = self.memory.predecessors(
                    indices=indices, horizon=policy_horizon, sequence_values=('states',),
                    initial_values=('internals/policy',)
                )
                policy_states = sequence_values['states']
                internals = initial_values['internals']
                policy_internals = initial_values['internals/policy']
            else:
                policy_horizons, sequence_values = self.memory.predecessors(
                    indices=indices, horizon=policy_horizon, sequence_values=('states',),
                    initial_values=()
                )
                policy_states = sequence_values['states']
                internals = policy_internals = TensorDict()
            # Optimize !!!!!
            baseline_horizon = self.baseline.past_horizon(on_policy=False)
            if self.separate_baseline:
                if len(self.internals_spec['baseline']) > 0:
                    baseline_horizons, sequence_values, initial_values = self.memory.predecessors(
                        indices=indices, horizon=baseline_horizon, sequence_values=('states',),
                        initial_values=('internals/baseline',)
                    )
                    baseline_states = sequence_values['states']
                    internals = initial_values['internals']
                    baseline_internals = initial_values['internals/baseline']
                else:
                    baseline_horizons, sequence_values = self.memory.predecessors(
                        indices=indices, horizon=baseline_horizon, sequence_values=('states',),
                        initial_values=()
                    )
                    baseline_states = sequence_values['states']
                    internals = baseline_internals = TensorDict()
            else:
                if len(self.internals_spec['policy']) > 0:
                    baseline_horizons, sequence_values, initial_values = self.memory.predecessors(
                        indices=indices, horizon=baseline_horizon, sequence_values=('states',),
                        initial_values=('internals/policy',)
                    )
                    baseline_states = sequence_values['states']
                    internals = initial_values['internals']
                    baseline_internals = initial_values['internals/policy']
                else:
                    baseline_horizons, sequence_values = self.memory.predecessors(
                        indices=indices, horizon=baseline_horizon, sequence_values=('states',),
                        initial_values=()
                    )
                    baseline_states = sequence_values['states']
                    internals = baseline_internals = TensorDict()

        # Retrieve auxiliaries, actions, reward
        if self.gae_decay.is_constant(value=0.0):
            values = self.memory.retrieve(
                indices=indices, values=('auxiliaries', 'actions', 'reward')
            )
        else:
            values = self.memory.retrieve(
                indices=indices, values=('auxiliaries', 'actions', 'reward', 'terminal')
            )
            terminal = values['terminal']
        auxiliaries = values['auxiliaries']
        actions = values['actions']
        reward = values['reward']

        # Return estimation
        if self.predict_horizon_values == 'late':
            reward = self._complete_horizon_values(
                indices=indices, internals=internals, reward=reward
            )

        dependencies = [reward]
        if self.summaries == 'all' or 'reward' in self.summaries or \
                self.tracking == 'all' or 'reward' in self.tracking:
            if self.summaries == 'all' or 'reward' in self.summaries:
                summarizer = self.summarizer.as_default()
                summarizer.__enter__()
            else:
                summarizer = None
            x = tf.math.reduce_mean(input_tensor=reward, axis=0)
            if summarizer is not None:
                dependencies.append(tf.summary.scalar(
                    name='update-return', data=x, step=self.updates
                ))
            dependencies.extend(self.track(label='reward', name='update-return', data=x))
            if summarizer is not None:
                summarizer.__exit__(None, None, None)

        if self.return_processing is not None:
            with tf.control_dependencies(control_inputs=dependencies):
                reward = self.return_processing.apply(
                    x=reward, deterministic=true, independent=False
                )

                dependencies = [reward]
                if self.summaries == 'all' or 'reward' in self.summaries or \
                        self.tracking == 'all' or 'reward' in self.tracking:
                    if self.summaries == 'all' or 'reward' in self.summaries:
                        summarizer = self.summarizer.as_default()
                        summarizer.__enter__()
                    else:
                        summarizer = None
                    x = tf.math.reduce_mean(input_tensor=reward, axis=0)
                    if summarizer is not None:
                        dependencies.append(tf.summary.scalar(
                            name='update-processed-return', data=x, step=self.updates
                        ))
                    dependencies.extend(self.track(
                        label='reward', name='update-processed-return', data=x
                    ))
                    if summarizer is not None:
                        summarizer.__exit__(None, None, None)

        baseline_arguments = TensorDict(
            states=baseline_states, horizons=baseline_horizons, internals=baseline_internals,
            auxiliaries=auxiliaries, actions=actions, reward=reward
        )
        if self.baseline_objective is not None:
            baseline_arguments['reference'] = self.baseline_objective.reference(
                states=baseline_states, horizons=baseline_horizons, internals=baseline_internals,
                auxiliaries=auxiliaries, actions=actions, policy=self.baseline
            )

        if self.baseline_optimizer is not None and self.estimate_advantage != 'early':
            def fn_kl_divergence(
                *, states, horizons, internals, auxiliaries, actions, reward, reference
            ):
                reference = self.baseline.kldiv_reference(
                    states=states, horizons=horizons, internals=internals, auxiliaries=auxiliaries
                )
                return self.baseline.kl_divergence(
                    states=states, horizons=horizons, internals=internals, auxiliaries=auxiliaries,
                    reference=reference
                )

            variables = tuple(self.baseline.trainable_variables)

            kwargs = dict()
            try:
                ordered_names = [variable.name for variable in variables]
                kwargs['source_variables'] = tuple(sorted(
                    self.policy.trainable_variables,
                    key=(lambda x: ordered_names.index(x.name.replace('/policy/', '/baseline/')))
                ))
            except ValueError:
                pass

            dependencies.extend(baseline_arguments.flatten())

            # Optimization
            with tf.control_dependencies(control_inputs=dependencies):
                optimized = self.baseline_optimizer.update(
                    arguments=baseline_arguments, variables=variables, fn_loss=self.baseline_loss,
                    fn_kl_divergence=fn_kl_divergence, **kwargs
                )
                dependencies = [optimized]

        with tf.control_dependencies(control_inputs=dependencies):
            if self.estimate_advantage is not False and not self.advantage_in_loss:
                if self.predict_action_values:
                    # Use past actions since advantage R(s,a) - Q(s,a)
                    baseline_prediction = self.baseline.action_value(
                        states=baseline_states, horizons=baseline_horizons,
                        internals=baseline_internals, auxiliaries=auxiliaries, actions=actions
                    )
                else:
                    baseline_prediction = self.baseline.state_value(
                        states=baseline_states, horizons=baseline_horizons,
                        internals=baseline_internals, auxiliaries=auxiliaries
                    )
                reward = reward - baseline_prediction

                dependencies = [reward]
                if self.summaries == 'all' or 'reward' in self.summaries or \
                        self.tracking == 'all' or 'reward' in self.tracking:
                    if self.summaries == 'all' or 'reward' in self.summaries:
                        summarizer = self.summarizer.as_default()
                        summarizer.__enter__()
                    else:
                        summarizer = None
                    x = tf.math.reduce_mean(input_tensor=reward, axis=0)
                    if summarizer is not None:
                        dependencies.append(tf.summary.scalar(
                            name='update-advantage', data=x, step=self.updates
                        ))
                    dependencies.extend(self.track(
                        label='reward', name='update-advantage', data=x
                    ))
                    if summarizer is not None:
                        summarizer.__exit__(None, None, None)

                if self.advantage_processing is not None:
                    with tf.control_dependencies(control_inputs=dependencies):
                        reward = self.advantage_processing.apply(
                            x=reward, deterministic=true, independent=False
                        )

                        dependencies = [reward]
                        if self.summaries == 'all' or 'reward' in self.summaries or \
                                self.tracking == 'all' or 'reward' in self.tracking:
                            if self.summaries == 'all' or 'reward' in self.summaries:
                                summarizer = self.summarizer.as_default()
                                summarizer.__enter__()
                            else:
                                summarizer = None
                            x = tf.math.reduce_mean(input_tensor=reward, axis=0)
                            if summarizer is not None:
                                dependencies.append(tf.summary.scalar(
                                    name='update-processed-advantage', data=x,
                                    step=self.updates
                                ))
                            dependencies.extend(self.track(
                                label='reward', name='update-processed-advantage', data=x
                            ))
                            if summarizer is not None:
                                summarizer.__exit__(None, None, None)

                if not self.gae_decay.is_constant(value=0.0):
                    with tf.control_dependencies(control_inputs=dependencies):
                        # Requires consistent batch!!!
                        zero_float = tf_util.constant(value=0.0, dtype='float')
                        reward_discount = self.reward_discount.value()
                        gae_decay = self.gae_decay.value()

                        # Discounted cumulative sum
                        def recursive_gae(next_gae, advantage_terminal):
                            current_advantage, current_terminal = advantage_terminal
                            next_gae = tf.where(
                                condition=(current_terminal == zero), x=next_gae, y=zero_float
                            )
                            return current_advantage + reward_discount * gae_decay * next_gae

                        reward = tf.scan(
                            fn=recursive_gae, elems=(reward, terminal), initializer=zero_float,
                            reverse=True
                        )

                        dependencies = [reward]
                        if self.summaries == 'all' or 'reward' in self.summaries or \
                                self.tracking == 'all' or 'reward' in self.tracking:
                            if self.summaries == 'all' or 'reward' in self.summaries:
                                summarizer = self.summarizer.as_default()
                                summarizer.__enter__()
                            else:
                                summarizer = None
                            x = tf.math.reduce_mean(input_tensor=reward, axis=0)
                            if summarizer is not None:
                                dependencies.append(tf.summary.scalar(
                                    name='update-gae', data=x, step=self.updates
                                ))
                            dependencies.extend(self.track(
                                label='reward', name='update-gae', data=x
                            ))
                            if summarizer is not None:
                                summarizer.__exit__(None, None, None)

        if self.baseline_optimizer is None:
            policy_only_internals = policy_internals['policy']
        else:
            policy_only_internals = policy_internals
        reference = self.objective.reference(
            states=policy_states, horizons=policy_horizons, internals=policy_only_internals,
            auxiliaries=auxiliaries, actions=actions, policy=self.policy
        )
        if self.baseline_objective is not None and self.baseline_loss_weight is not None and \
                not self.baseline_loss_weight.is_constant(value=0.0):
            reference = TensorDict(policy=reference, baseline=baseline_arguments['reference'])

        policy_arguments = TensorDict(
            states=policy_states, horizons=policy_horizons, internals=policy_internals,
            auxiliaries=auxiliaries, actions=actions, reward=reward, reference=reference
        )

        if self.estimate_advantage is not False and self.advantage_in_loss:
            variables = tuple(self.trainable_variables)

            def fn_loss(*, states, horizons, internals, auxiliaries, actions, reward, reference):
                assertions = list()
                if self.config.create_tf_assertions:
                    past_horizon = self.baseline.past_horizon(on_policy=False)
                    # TODO: remove restriction
                    assertions.append(tf.debugging.assert_less_equal(
                        x=(horizons[:, 1] - one), y=past_horizon,
                        message="Baseline horizon cannot be greater than policy horizon."
                    ))
                with tf.control_dependencies(control_inputs=assertions):
                    if self.predict_action_values:
                        # Use past actions since advantage R(s,a) - Q(s,a)
                        baseline_prediction = self.baseline.action_value(
                            states=states, horizons=horizons, internals=internals['baseline'],
                            auxiliaries=auxiliaries, actions=actions
                        )
                    else:
                        baseline_prediction = self.baseline.state_value(
                            states=states, horizons=horizons, internals=internals['baseline'],
                            auxiliaries=auxiliaries
                        )
                    reward = reward - baseline_prediction

                    def fn_summary1():
                        return tf.math.reduce_mean(input_tensor=reward, axis=0)

                    dependencies = self.summary(
                        label='reward', name='update-advantage', data=fn_summary1, step='updates'
                    )
                    dependencies.extend(self.track(
                        label='reward', name='update-advantage', data=fn_summary1
                    ))

                    if self.advantage_processing is not None:
                        with tf.control_dependencies(control_inputs=dependencies):
                            reward = self.advantage_processing.apply(
                                x=reward, deterministic=true, independent=False
                            )

                            def fn_summary2():
                                return tf.math.reduce_mean(input_tensor=reward, axis=0)

                            dependencies = self.summary(
                                label='reward', name='update-processed-advantage',
                                data=fn_summary2, step='updates'
                            )
                            dependencies.extend(self.track(
                                label='reward', name='update-processed-advantage', data=fn_summary2
                            ))

                with tf.control_dependencies(control_inputs=dependencies):
                    return self.loss(
                        states=states, horizons=horizons, internals=internals,
                        auxiliaries=auxiliaries, actions=actions, reward=reward, reference=reference
                    )

        else:
            variables = tuple(self.policy.trainable_variables)
            fn_loss = self.loss

        def fn_kl_divergence(
            *, states, horizons, internals, auxiliaries, actions, reward, reference
        ):
            if self.baseline_optimizer is None:
                internals = internals['policy']
            # TODO: Policy require
            reference = self.policy.kldiv_reference(
                states=states, horizons=horizons, internals=internals, auxiliaries=auxiliaries
            )
            return self.policy.kl_divergence(
                states=states, horizons=horizons, internals=internals, auxiliaries=auxiliaries,
                reference=reference
            )

        kwargs = dict()
        if self.separate_baseline:
            try:
                ordered_names = [variable.name for variable in variables]
                kwargs['source_variables'] = tuple(sorted(
                    self.baseline.trainable_variables,
                    key=(lambda x: ordered_names.index(x.name.replace('/baseline/', '/policy/')))
                ))
            except ValueError:
                pass
        # if self.global_model is not None:
        #     assert 'global_variables' not in kwargs
        #     kwargs['global_variables'] = tuple(self.global_model.trainable_variables)

        dependencies.extend(policy_arguments.flatten())

        # Hack: KL divergence summary: reference before update
        if isinstance(self.policy, StochasticPolicy) and (
            self.summaries == 'all' or 'kl-divergence' in self.summaries or
            self.tracking == 'all' or 'kl-divergence' in self.tracking
        ):
            kldiv_reference = self.policy.kldiv_reference(
                states=policy_states, horizons=policy_horizons, internals=policy_only_internals,
                auxiliaries=auxiliaries
            )
            dependencies.extend(kldiv_reference.flatten())

        # Optimization
        with tf.control_dependencies(control_inputs=dependencies):
            optimized = self.optimizer.update(
                arguments=policy_arguments, variables=variables, fn_loss=fn_loss,
                fn_kl_divergence=fn_kl_divergence, **kwargs
            )
            dependencies = [optimized]

        if self.baseline_optimizer is not None and self.estimate_advantage == 'early':
            def fn_kl_divergence(
                *, states, horizons, internals, auxiliaries, actions, reward, reference
            ):
                reference = self.baseline.kldiv_reference(
                    states=states, horizons=horizons, internals=internals, auxiliaries=auxiliaries
                )
                return self.baseline.kl_divergence(
                    states=states, horizons=horizons, internals=internals, auxiliaries=auxiliaries,
                    reference=reference
                )

            variables = tuple(self.baseline.trainable_variables)

            kwargs = dict()
            try:
                ordered_names = [variable.name for variable in variables]
                kwargs['source_variables'] = tuple(sorted(
                    self.policy.trainable_variables,
                    key=(lambda x: ordered_names.index(x.name.replace('/policy/', '/baseline/')))
                ))
            except ValueError:
                pass

            dependencies.extend(baseline_arguments.flatten())

            # Optimization
            with tf.control_dependencies(control_inputs=dependencies):
                optimized = self.baseline_optimizer.update(
                    arguments=baseline_arguments, variables=variables, fn_loss=self.baseline_loss,
                    fn_kl_divergence=fn_kl_divergence, **kwargs
                )
                dependencies = [optimized]

        # Update summaries
        with tf.control_dependencies(control_inputs=dependencies):
            dependencies = list()

            # Entropy summaries
            if isinstance(self.policy, StochasticPolicy) and (
                self.summaries == 'all' or 'entropy' in self.summaries or
                self.tracking == 'all' or 'entropy' in self.tracking
            ):
                if self.summaries == 'all' or 'entropy' in self.summaries:
                    summarizer = self.summarizer.as_default()
                    summarizer.__enter__()
                else:
                    summarizer = None
                if len(self.actions_spec) > 1:
                    entropies = self.policy.entropies(
                        states=policy_states, horizons=policy_horizons,
                        internals=policy_only_internals, auxiliaries=auxiliaries
                    )
                    for name, spec in self.actions_spec.items():
                        entropies[name] = tf.reshape(tensor=entropies[name], shape=(-1,))
                        entropy = tf.math.reduce_mean(input_tensor=entropies[name], axis=0)
                        if summarizer is not None:
                            dependencies.append(tf.summary.scalar(
                                name=('entropies/' + name), data=entropy, step=self.updates
                            ))
                        dependencies.extend(self.track(
                            label='entropy', name=('entropies/' + name), data=entropy
                        ))
                    entropy = tf.concat(values=tuple(entropies.values()), axis=0)
                else:
                    entropy = self.policy.entropy(
                        states=policy_states, horizons=policy_horizons,
                        internals=policy_only_internals, auxiliaries=auxiliaries
                    )
                entropy = tf.math.reduce_mean(input_tensor=entropy, axis=0)
                if summarizer is not None:
                    dependencies.append(
                        tf.summary.scalar(name='entropy', data=entropy, step=self.updates)
                    )
                dependencies.extend(self.track(label='entropy', name='entropy', data=entropy))
                if summarizer is not None:
                    summarizer.__exit__(None, None, None)

            # KL divergence summaries
            if isinstance(self.policy, StochasticPolicy) and (
                self.summaries == 'all' or 'kl-divergence' in self.summaries or
                self.tracking == 'all' or 'kl-divergence' in self.tracking
            ):
                if self.summaries == 'all' or 'kl-divergence' in self.summaries:
                    summarizer = self.summarizer.as_default()
                    summarizer.__enter__()
                else:
                    summarizer = None
                if len(self.actions_spec) > 1:
                    kl_divs = self.policy.kl_divergences(
                        states=policy_states, horizons=policy_horizons,
                        internals=policy_only_internals, auxiliaries=auxiliaries,
                        reference=kldiv_reference
                    )
                    for name, spec in self.actions_spec.items():
                        kl_divs[name] = tf.reshape(tensor=kl_divs[name], shape=(-1,))
                        kl_div = tf.math.reduce_mean(input_tensor=kl_divs[name], axis=0)
                        if summarizer is not None:
                            dependencies.append(tf.summary.scalar(
                                name=('kl-divergences/' + name), data=kl_div, step=self.updates
                            ))
                        dependencies.extend(self.track(
                            label='kl-divergence', name=('kl-divergences/' + name), data=kl_div
                        ))
                    kl_div = tf.concat(values=tuple(kl_divs.values()), axis=0)
                else:
                    kl_div = self.policy.kl_divergence(
                        states=policy_states, horizons=policy_horizons,
                        internals=policy_only_internals, auxiliaries=auxiliaries,
                        reference=kldiv_reference
                    )
                kl_div = tf.math.reduce_mean(input_tensor=kl_div, axis=0)
                if summarizer is not None:
                    dependencies.append(
                        tf.summary.scalar(name='kl-divergence', data=kl_div, step=self.updates)
                    )
                dependencies.extend(
                    self.track(label='kl-divergence', name='kl-divergence', data=kl_div)
                )
                if summarizer is not None:
                    summarizer.__exit__(None, None, None)

        # Increment update
        with tf.control_dependencies(control_inputs=dependencies):
            assignment = self.updates.assign_add(delta=one, read_value=False)

        with tf.control_dependencies(control_inputs=(assignment,)):
            dependencies = list()

            # Variables summaries
            if self.summaries == 'all' or 'variables' in self.summaries:
                with self.summarizer.as_default():
                    for variable in self.trainable_variables:
                        name = variable.name
                        assert name.startswith(self.name + '/') and name[-2:] == ':0'
                        name = 'variables/' + name[len(self.name) + 1: -2]
                        x = tf.math.reduce_mean(input_tensor=variable)
                        dependencies.append(tf.summary.scalar(name=name, data=x, step=self.updates))

        with tf.control_dependencies(control_inputs=dependencies):
            return tf_util.identity(input=optimized)

    def _complete_horizon_values(self, indices, internals, reward):
        zero = tf_util.constant(value=0, dtype='int')
        one = tf_util.constant(value=1, dtype='int')
        true = tf_util.constant(value=True, dtype='bool')
        reward_horizon = self.reward_horizon.value()
        reward_discount = self.reward_discount.value()

        # TODO: no need for memory if update episode-based (or not random replay?)

        # Internal values to retrieve, depending on different internals configurations
        baseline_internals_values = 'internals/baseline'
        if self.predict_action_values and self.separate_baseline:
            internals_values = 'internals'
        elif self.separate_baseline:
            if len(self.internals_spec['baseline']) > 0:
                internals_values = 'internals/baseline'
            else:
                internals_values = None
        else:
            if len(self.internals_spec['policy']) > 0:
                internals_values = 'internals/policy'
                baseline_internals_values = 'internals/policy'
            else:
                internals_values = None

        if self.baseline.max_past_horizon(on_policy=False) == 0:
            # Horizons indexing tensor
            batch_size = tf_util.cast(x=tf.shape(input=indices)[0], dtype='int')
            starts = tf.range(batch_size)
            lengths = tf.ones_like(input=indices)
            horizons = tf.stack(values=(starts, lengths), axis=1)

            # TODO: remove restriction
            if self.predict_action_values and self.separate_baseline:
                assert self.policy.max_past_horizon(on_policy=False) == 0

            # Retrieve horizon values from memory
            values = ('states', 'auxiliaries', 'terminal')
            if internals_values is not None:
                values += (internals_values,)
            offsets, values = self.memory.successors(
                indices=indices, horizon=reward_horizon, sequence_values=(), final_values=values
            )
            states = values['states']
            policy_internals = values.get('internals/policy')
            baseline_internals = values.get(baseline_internals_values, TensorDict())
            auxiliaries = values['auxiliaries']
            terminal = values['terminal']

            # -1 since successors length >= 1
            offsets = offsets - one

        else:
            baseline_horizon = self.baseline.past_horizon(on_policy=False)
            assertions = list()
            if self.config.create_tf_assertions and self.predict_action_values:
                policy_horizon = self.policy.past_horizon(on_policy=False)
                # TODO: remove restriction
                assertions.append(tf.debugging.assert_equal(
                    x=policy_horizon, y=baseline_horizon,
                    message="Policy and baseline cannot depend on a different number of "
                            "previous states if predict_action_values is True."
                ))

            with tf.control_dependencies(control_inputs=assertions):
                # (Tried to do this more efficiently by differentiating between
                # reward horizon >/=/< baseline horizon, but gets too complex since
                # it needs to take into account episode start/end edge cases.)

                # Retrieve horizon values from memory
                offsets, values = self.memory.successors(
                    indices=indices, horizon=reward_horizon, sequence_values=(),
                    final_values=('auxiliaries', 'terminal')
                )
                auxiliaries = values['auxiliaries']
                terminal = values['terminal']

                # -1 since successors length >= 1
                offsets = offsets - one

                # Retrieve baseline states sequence and initial internals from memory
                if internals_values is None:
                    horizons, sequence_values = self.memory.predecessors(
                        indices=(indices + offsets), horizon=baseline_horizon,
                        sequence_values=('states',), initial_values=()
                    )
                    policy_internals = None
                    baseline_internals = TensorDict()
                else:
                    horizons, sequence_values, initial_values = self.memory.predecessors(
                        indices=indices, horizon=(baseline_horizon - reward_horizon),
                        sequence_values=('states',), initial_values=(internals_values,)
                    )
                    policy_internals = initial_values.get('internals/policy')
                    baseline_internals = initial_values.get(baseline_internals_values, TensorDict())
                states = sequence_values['states']

        # Predict horizon values
        if self.predict_action_values:
            actions, _ = self.policy.act(
                states=states, horizons=horizons, internals=policy_internals,
                auxiliaries=auxiliaries, deterministic=true, independent=True
            )
            horizon_values = self.baseline.action_value(
                states=states, horizons=horizons, internals=baseline_internals,
                auxiliaries=auxiliaries, actions=actions
            )
        else:
            horizon_values = self.baseline.state_value(
                states=states, horizons=horizons, internals=baseline_internals,
                auxiliaries=auxiliaries
            )

        # Value horizon assertions
        assertions = list()
        if self.config.create_tf_assertions:
            assertions.append(tf.debugging.assert_greater_equal(x=offsets, y=zero))
            if self.baseline.max_past_horizon(on_policy=False) == 0:
                baseline_horizon = self.baseline.past_horizon(on_policy=False)
            assertions.append(tf.debugging.assert_less_equal(x=offsets, y=reward_horizon))

        # Add appropriately discounted horizon values to reward
        with tf.control_dependencies(control_inputs=assertions):
            # Pow numerically stable since 0.0 <= discount <= 1.0
            discounts = tf.math.pow(x=reward_discount, y=tf_util.cast(x=offsets, dtype='float'))
            if not self.predict_terminal_values:
                is_terminal = tf.math.equal(x=terminal, y=one)
                zeros = tf.zeros_like(input=discounts)
                discounts = tf.where(condition=is_terminal, x=zeros, y=discounts)

        return reward + discounts * horizon_values

    @tf_function(num_args=7)
    def loss(self, *, states, horizons, internals, auxiliaries, actions, reward, reference):
        if self.baseline_optimizer is None:
            policy_internals = internals['policy']
        else:
            policy_internals = internals
        if self.baseline_objective is not None and self.baseline_loss_weight is not None and \
                not self.baseline_loss_weight.is_constant(value=0.0):
            policy_reference = reference['policy']
        else:
            policy_reference = reference

        # Loss per instance
        loss = self.objective.loss(
            states=states, horizons=horizons, internals=policy_internals, auxiliaries=auxiliaries,
            actions=actions, reward=reward, reference=policy_reference, policy=self.policy,
            baseline=(self.baseline if self.separate_baseline else None)
        )

        # Objective loss
        loss = tf.math.reduce_mean(input_tensor=loss, axis=0)
        dependencies = self.summary(
            label='loss', name='losses/policy-objective-loss', data=loss, step='updates'
        )
        dependencies.extend(self.track(label='loss', name='policy-objective-loss', data=loss))

        # Regularization losses
        regularization_loss = self.regularize(
            states=states, horizons=horizons, internals=policy_internals, auxiliaries=auxiliaries
        )
        dependencies.extend(self.summary(
            label='loss', name='losses/policy-regularization-loss', data=regularization_loss,
            step='updates'
        ))
        dependencies.extend(
            self.track(label='loss', name='policy-regularization-loss', data=regularization_loss)
        )
        loss += regularization_loss

        # Baseline loss
        if self.baseline_loss_weight is not None and \
                not self.baseline_loss_weight.is_constant(value=0.0):
            if self.separate_baseline:
                baseline_internals = internals['baseline']
            else:
                baseline_internals = policy_internals
            if self.baseline_objective is not None:
                baseline_reference = reference['baseline']
            else:
                baseline_reference = policy_reference

            zero = tf_util.constant(value=0.0, dtype='float')
            baseline_loss_weight = self.baseline_loss_weight.value()

            def no_baseline_loss():
                return zero

            def apply_baseline_loss():
                baseline_loss = self.baseline_loss(
                    states=states, horizons=horizons, internals=baseline_internals,
                    auxiliaries=auxiliaries, actions=actions, reward=reward,
                    reference=baseline_reference
                )
                return baseline_loss_weight * baseline_loss

            loss += tf.cond(
                pred=tf.math.equal(x=baseline_loss_weight, y=zero),
                true_fn=no_baseline_loss, false_fn=apply_baseline_loss
            )

        dependencies.extend(self.summary(
            label='loss', name='losses/policy-loss', data=loss, step='updates'
        ))
        dependencies.extend(self.track(label='loss', name='policy-loss', data=loss))

        with tf.control_dependencies(control_inputs=dependencies):
            return tf_util.identity(input=loss)

    @tf_function(num_args=4, overwrites_signature=True)
    def regularize(self, *, states, horizons, internals, auxiliaries):
        regularization_loss = super().regularize()

        # Entropy regularization
        if not self.entropy_regularization.is_constant(value=0.0):
            zero = tf_util.constant(value=0.0, dtype='float')
            entropy_regularization = self.entropy_regularization.value()

            def no_entropy_regularization():
                return zero

            def apply_entropy_regularization():
                entropy = self.policy.entropy(
                    states=states, horizons=horizons, internals=internals, auxiliaries=auxiliaries
                )
                entropy = tf.math.reduce_mean(input_tensor=entropy, axis=0)
                return -entropy_regularization * entropy

            regularization_loss += tf.cond(
                pred=tf.math.equal(x=entropy_regularization, y=zero),
                true_fn=no_entropy_regularization, false_fn=apply_entropy_regularization
            )

        return regularization_loss

    @tf_function(num_args=7)
    def baseline_loss(
        self, *, states, horizons, internals, auxiliaries, actions, reward, reference
    ):
        # Loss per instance
        loss = self.baseline_objective.loss(
            states=states, horizons=horizons, internals=internals, auxiliaries=auxiliaries,
            actions=actions, reward=reward, reference=reference, policy=self.baseline
        )

        # Objective loss
        loss = tf.math.reduce_mean(input_tensor=loss, axis=0)

        dependencies = list()
        if self.separate_baseline:
            dependencies.extend(self.summary(
                label='loss', name='losses/baseline-objective-loss', data=loss, step='updates'
            ))
            dependencies.extend(
                self.track(label='loss', name='baseline-objective-loss', data=loss)
            )

            # Regularization losses
            regularization_loss = self.baseline.regularize()
            dependencies.extend(self.summary(
                label='loss', name='losses/baseline-regularization-loss',
                data=regularization_loss, step='updates'
            ))
            dependencies.extend(self.track(
                label='loss', name='baseline-regularization-loss', data=regularization_loss
            ))
            loss += regularization_loss

        dependencies.extend(self.summary(
            label='loss', name='losses/baseline-loss', data=loss, step='updates'
        ))
        dependencies.extend(self.track(label='loss', name='baseline-loss', data=loss))

        with tf.control_dependencies(control_inputs=dependencies):
            return tf_util.identity(input=loss)
