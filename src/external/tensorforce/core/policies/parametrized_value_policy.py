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

import tensorflow as tf

from tensorforce import TensorforceError
from tensorforce.core import layer_modules, ModuleDict, TensorDict, TensorSpec, TensorsSpec, \
    tf_function, tf_util
from tensorforce.core.policies import ParametrizedPolicy, ValuePolicy


class ParametrizedValuePolicy(ValuePolicy, ParametrizedPolicy):
    """
    Policy which parametrizes independent action-/advantage-/state-value functions per action and
    optionally a state-value function, conditioned on the output of a central neural network
    processing the input state (specification key: `parametrized_value_policy`).

    Args:
        network ('auto' | specification): Policy network configuration, see
            [networks](../modules/networks.html)
            (<span style="color:#00C000"><b>default</b></span>: 'auto', automatically configured
            network).
        single_output (bool): Whether the network returns a single embedding tensor or, in the case
            of multiple action components, specifies additional outputs for some/all action/state
            value functions, via registered tensors with name "[ACTION]-embedding" or
            "state-embedding"/"[ACTION]-state-embedding" depending on the state_value_mode argument
            (<span style="color:#00C000"><b>default</b></span>: single output).
        state_value_mode ('implicit' | 'separate' | 'separate-per-action'): Whether to compute the
            state value implicitly as maximum action value (like DQN), or as either a single
            separate state-value function or a function per action (like DuelingDQN)
            (<span style="color:#00C000"><b>default</b></span>: single separate state-value
            function).
        device (string): Device name
            (<span style="color:#00C000"><b>default</b></span>: inherit value of parent module).
        l2_regularization (float >= 0.0): Scalar controlling L2 regularization
            (<span style="color:#00C000"><b>default</b></span>: inherit value of parent module).
        name (string): <span style="color:#0000C0"><b>internal use</b></span>.
        states_spec (specification): <span style="color:#0000C0"><b>internal use</b></span>.
        auxiliaries_spec (specification): <span style="color:#0000C0"><b>internal use</b></span>.
        internals_spec (specification): <span style="color:#0000C0"><b>internal use</b></span>.
        actions_spec (specification): <span style="color:#0000C0"><b>internal use</b></span>.
    """

    # Network first
    def __init__(
        self, network='auto', *, single_output=True, state_value_mode='separate', device=None,
        l2_regularization=None, name=None, states_spec=None, auxiliaries_spec=None,
        internals_spec=None, actions_spec=None
    ):
        super().__init__(
            device=device, l2_regularization=l2_regularization, name=name, states_spec=states_spec,
            auxiliaries_spec=auxiliaries_spec, actions_spec=actions_spec
        )

        if not all(spec.type in ('bool', 'int') for spec in self.actions_spec.values()):
            raise TensorforceError.value(
                name='ParametrizedValuePolicy', argument='actions_spec', value=actions_spec,
                hint='types not bool/int'
            )

        # State value mode
        if state_value_mode not in ('implicit', 'separate', 'separate-per-action'):
            raise TensorforceError.value(
                name='ParametrizedValuePolicy', argument='state_value_mode', value=state_value_mode,
                hint='not from {implicit,separate,separate-per-action}'
            )
        self.state_value_mode = state_value_mode

        if single_output:
            outputs = None
        elif self.actions_spec.is_singleton():
            if self.state_value_mode == 'implicit':
                outputs = ('action-embedding',)
            else:
                outputs = ('action-embedding', 'state-embedding')
        else:
            outputs = tuple(name + '-embedding' for name in self.actions_spec)
            if self.state_value_mode == 'separate':
                outputs += ('state-embedding',)
            elif self.state_value_mode == 'separate-per-action':
                outputs += tuple(name + '-state-embedding' for name in self.actions_spec)
        ParametrizedPolicy.__init__(
            self=self, network=network, inputs_spec=self.states_spec, outputs=outputs
        )
        output_spec = self.network.output_spec()
        if not isinstance(output_spec, TensorsSpec):
            output_spec = TensorsSpec(embedding=output_spec)

        # Action values
        def function(name, spec):
            if name is None:
                input_name = 'action-embedding'
                name = 'action_value'
            else:
                input_name = name + '-embedding'
                name = name + '_action_value'
            if spec.type == 'bool':
                return self.submodule(
                    name=name, module='linear', modules=layer_modules, size=(spec.size * 2),
                    input_spec=output_spec.get(input_name, output_spec['embedding'])
                )
            elif spec.type == 'int':
                return self.submodule(
                    name=name, module='linear', modules=layer_modules,
                    size=(spec.size * spec.num_values),
                    input_spec=output_spec.get(input_name, output_spec['embedding'])
                )

        self.a_values = self.actions_spec.fmap(function=function, cls=ModuleDict, with_names=True)

        if self.state_value_mode == 'separate':
            # State value
            self.s_value = self.submodule(
                name='value', module='linear', modules=layer_modules, size=0,
                input_spec=output_spec.get('state-embedding', output_spec['embedding'])
            )

        elif self.state_value_mode == 'separate-per-action':
            # State values per action

            def function(name, spec):
                if name is None:
                    input_name = 'state-embedding'
                    name = 'state_value'
                else:
                    input_name = name + '-state-embedding'
                    name = name + '_state_value'
                return self.submodule(
                    name=name, module='linear', modules=layer_modules, size=spec.size,
                    input_spec=output_spec.get(input_name, output_spec['embedding'])
                )

            self.s_values = self.states_spec.fmap(
                function=function, cls=ModuleDict, with_names=True
            )

    def get_architecture(self):
        architecture = 'Network:  {}'.format(
            self.network.get_architecture().replace('\n', '\n    ')
        )
        if self.a_values.is_singleton():
            architecture += 'Action-value:  {}'.format(
                self.a_values.singleton().get_architecture().replace('\n', '\n    ')
            )
        else:
            architecture += 'Action-values:'
            for name, a_value in self.a_values.items():
                architecture += '\n    {}:  {}'.format(
                    name, a_value.get_architecture().replace('\n', '\n    ')
                )
        if self.state_value_mode == 'separate':
            architecture += 'State-value:  {}'.format(
                self.s_value.get_architecture().replace('\n', '\n    ')
            )
        elif self.state_value_mode == 'separate-per-action':
            if self.s_values.is_singleton():
                architecture += 'State-value:  {}'.format(
                    self.s_values.singleton().get_architecture().replace('\n', '\n    ')
                )
            else:
                architecture += 'State-values:'
                for name, s_value in self.s_values.items():
                    architecture += '\n    {}:  {}'.format(
                        name, s_value.get_architecture().replace('\n', '\n    ')
                    )
        return architecture

    def initialize(self):
        super().initialize()

        for name, spec in self.actions_spec.items():
            if spec.type == 'bool':
                if name is None:
                    names = ['action-values/true', 'action-values/false']
                else:
                    names = ['action-values/' + name + '-true', 'action-values/' + name + '-false']
                spec = TensorSpec(type='float', shape=(spec.shape + (2,)))
            else:
                if name is None:
                    prefix = 'action-values/action'
                else:
                    prefix = 'action-values/' + name + '-action'
                names = [prefix + str(n) for n in range(spec.num_values)]
                spec = TensorSpec(type='float', shape=(spec.shape + (spec.num_values,)))

            self.register_summary(label='action-value', name=names)

            if name is None:
                name = 'action-values'
            else:
                name = name + '-values'

            self.register_tracking(label='action-value', name=name, spec=spec)

    def get_savedmodel_trackables(self):
        trackables = super().get_savedmodel_trackables()
        for a_value in self.a_values.values():
            for variable in a_value.variables:
                assert variable.name not in trackables
                trackables[variable.name] = variable
        if self.state_value_mode == 'separate':
            for variable in self.s_value.variables:
                assert variable.name not in trackables
                trackables[variable.name] = variable
        elif self.state_value_mode == 'separate-per-action':
            for s_value in self.s_values.values():
                for variable in s_value.variables:
                    assert variable.name not in trackables
                    trackables[variable.name] = variable
        return trackables

    @tf_function(num_args=5)
    def act(self, *, states, horizons, internals, auxiliaries, deterministic, independent):
        embedding, internals = self.network.apply(
            x=states, horizons=horizons, internals=internals, deterministic=deterministic,
            independent=independent
        )
        if not isinstance(embedding, TensorDict):
            embedding = TensorDict(embedding=embedding)

        if self.state_value_mode == 'implicit':

            def function(name, spec, a_value):
                if name is None:
                    x = embedding.get('action-embedding', embedding['embedding'])
                else:
                    x = embedding.get(name + '-embedding', embedding['embedding'])
                action_value = a_value.apply(x=x)
                if spec.type == 'bool':
                    shape = (-1,) + spec.shape + (2,)
                elif spec.type == 'int':
                    shape = (-1,) + spec.shape + (spec.num_values,)
                return tf.reshape(tensor=action_value, shape=shape)

            action_values = self.actions_spec.fmap(
                function=function, cls=TensorDict, with_names=True, zip_values=(self.a_values,)
            )

        elif self.state_value_mode == 'separate':
            state_value = self.s_value.apply(
                x=embedding.get('state-embedding', embedding['embedding'])
            )

            def function(name, spec, a_value):
                if name is None:
                    x = embedding.get('action-embedding', embedding['embedding'])
                else:
                    x = embedding.get(name + '-embedding', embedding['embedding'])
                advantage_value = a_value.apply(x=x)
                if spec.type == 'bool':
                    shape = (-1,) + spec.shape + (2,)
                elif spec.type == 'int':
                    shape = (-1,) + spec.shape + (spec.num_values,)
                advantage_value = tf.reshape(tensor=advantage_value, shape=shape)
                mean = tf.math.reduce_mean(input_tensor=advantage_value, axis=-1, keepdims=True)
                shape = (-1,) + tuple(1 for _ in range(spec.rank + 1))
                _state_value = tf.reshape(tensor=state_value, shape=shape)
                return _state_value + (advantage_value - mean)

            action_values = self.actions_spec.fmap(
                function=function, cls=TensorDict, with_names=True, zip_values=(self.a_values,)
            )

        elif self.state_value_mode == 'separate-per-action':

            def function(name, spec, s_value, a_value):
                if name is None:
                    state_value = s_value.apply(
                        x=embedding.get('state-embedding', embedding['embedding'])
                    )
                    advantage_value = a_value.apply(
                        x=embedding.get('action-embedding', embedding['embedding'])
                    )
                else:
                    state_value = s_value.apply(
                        x=embedding.get(name + '-state-embedding', embedding['embedding'])
                    )
                    advantage_value = a_value.apply(
                        x=embedding.get(name + '-embedding', embedding['embedding'])
                    )
                if spec.type == 'bool':
                    shape = (-1,) + spec.shape + (2,)
                elif spec.type == 'int':
                    shape = (-1,) + spec.shape + (spec.num_values,)
                advantage_value = tf.reshape(tensor=advantage_value, shape=shape)
                mean = tf.math.reduce_mean(input_tensor=advantage_value, axis=-1, keepdims=True)
                return tf.expand_dims(input=state_value, axis=-1) + (advantage_value - mean)

            action_values = self.actions_spec.fmap(
                function=function, cls=TensorDict, with_names=True,
                zip_values=(self.s_values, self.a_values)
            )

        def function(name, spec, action_value):
            if spec.type == 'bool':

                def fn_summary():
                    axis = range(spec.rank + 1)
                    values = tf.math.reduce_mean(input_tensor=action_value, axis=axis)
                    return [values[0], values[1]]

                if name is None:
                    names = ['action-values/true', 'action-values/false']
                else:
                    names = ['action-values/' + name + '-true', 'action-values/' + name + '-false']
                dependencies = self.summary(
                    label='action-value', name=names, data=fn_summary, step='timesteps'
                )

                def fn_tracking():
                    return tf.math.reduce_mean(input_tensor=action_value, axis=0)

                if name is None:
                    n = 'action-values'
                else:
                    n = name + '-values'
                dependencies = self.track(label='action-value', name=n, data=fn_tracking)

                with tf.control_dependencies(control_inputs=dependencies):
                    return (action_value[..., 0] > action_value[..., 1])

            elif spec.type == 'int':

                def fn_summary():
                    axis = range(spec.rank + 1)
                    values = tf.math.reduce_mean(input_tensor=action_value, axis=axis)
                    return [values[n] for n in range(spec.num_values)]

                if name is None:
                    prefix = 'action-values/action'
                else:
                    prefix = 'action-values/' + name + '-action'
                names = [prefix + str(n) for n in range(spec.num_values)]
                dependencies = self.summary(
                    label='action-value', name=names, data=fn_summary, step='timesteps'
                )

                def fn_tracking():
                    return tf.math.reduce_mean(input_tensor=action_value, axis=0)

                if name is None:
                    n = 'action-values'
                else:
                    n = name + '-values'
                dependencies = self.track(label='action-value', name=n, data=fn_tracking)

                with tf.control_dependencies(control_inputs=dependencies):
                    if self.config.enable_int_action_masking:
                        mask = auxiliaries[name]['mask']
                        min_float = tf_util.get_dtype(type='float').min
                        min_float = tf.fill(dims=tf.shape(input=action_value), value=min_float)
                        action_value = tf.where(condition=mask, x=action_value, y=min_float)
                    return tf.math.argmax(input=action_value, axis=-1, output_type=spec.tf_type())

        actions = self.actions_spec.fmap(
            function=function, cls=TensorDict, with_names=True, zip_values=(action_values,)
        )

        return actions, internals

    @tf_function(num_args=4)
    def state_value(self, *, states, horizons, internals, auxiliaries):
        if self.state_value_mode == 'separate':
            deterministic = tf_util.constant(value=True, dtype='bool')
            embedding, _ = self.network.apply(
                x=states, horizons=horizons, internals=internals, deterministic=deterministic,
                independent=True
            )
            if not isinstance(embedding, TensorDict):
                embedding = TensorDict(embedding=embedding)

            return self.s_value.apply(x=embedding.get('state-embedding', embedding['embedding']))

        else:
            return super().state_value(
                states=states, horizons=horizons, internals=internals, auxiliaries=auxiliaries
            )

    @tf_function(num_args=5)
    def action_values(self, *, states, horizons, internals, auxiliaries, actions):
        deterministic = tf_util.constant(value=True, dtype='bool')
        embedding, _ = self.network.apply(
            x=states, horizons=horizons, internals=internals, deterministic=deterministic,
            independent=True
        )
        if not isinstance(embedding, TensorDict):
            embedding = TensorDict(embedding=embedding)

        if self.state_value_mode == 'implicit':

            def function(name, spec, a_value, action):
                if name is None:
                    x = embedding.get('action-embedding', embedding['embedding'])
                else:
                    x = embedding.get(name + '-embedding', embedding['embedding'])
                action_value = a_value.apply(x=x)
                if spec.type == 'bool':
                    shape = (-1,) + spec.shape + (2,)
                elif spec.type == 'int':
                    shape = (-1,) + spec.shape + (spec.num_values,)
                action_value = tf.reshape(tensor=action_value, shape=shape)
                if spec.type == 'bool':
                    return tf.where(
                        condition=action, x=action_value[..., 0], y=action_value[..., 1]
                    )
                elif spec.type == 'int':
                    action = tf.expand_dims(input=action, axis=(spec.rank + 1))
                    action_value = tf.gather(
                        params=action_value, indices=action, batch_dims=(spec.rank + 1)
                    )
                    return tf.squeeze(input=action_value, axis=(spec.rank + 1))

            return self.actions_spec.fmap(
                function=function, cls=TensorDict, with_names=True,
                zip_values=(self.a_values, actions)
            )

        elif self.state_value_mode == 'separate':
            state_value = self.s_value.apply(
                x=embedding.get('state-embedding', embedding['embedding'])
            )

            def function(name, spec, a_value, action):
                if name is None:
                    x = embedding.get('action-embedding', embedding['embedding'])
                else:
                    x = embedding.get(name + '-embedding', embedding['embedding'])
                advantage_value = a_value.apply(x=x)
                if spec.type == 'bool':
                    shape = (-1,) + spec.shape + (2,)
                elif spec.type == 'int':
                    shape = (-1,) + spec.shape + (spec.num_values,)
                advantage_value = tf.reshape(tensor=advantage_value, shape=shape)
                mean = tf.math.reduce_mean(input_tensor=advantage_value, axis=-1, keepdims=True)
                shape = (-1,) + tuple(1 for _ in range(spec.rank + 1))
                _state_value = tf.reshape(tensor=state_value, shape=shape)
                action_value = _state_value + (advantage_value - mean)
                if spec.type == 'bool':
                    return tf.where(
                        condition=action, x=action_value[..., 0], y=action_value[..., 1]
                    )
                elif spec.type == 'int':
                    action = tf.expand_dims(input=action, axis=(spec.rank + 1))
                    action_value = tf.gather(
                        params=action_value, indices=action, batch_dims=(spec.rank + 1)
                    )
                    return tf.squeeze(input=action_value, axis=(spec.rank + 1))

            return self.actions_spec.fmap(
                function=function, cls=TensorDict, with_names=True,
                zip_values=(self.a_values, actions)
            )

        elif self.state_value_mode == 'separate-per-action':

            def function(name, spec, s_value, a_value, action):
                if name is None:
                    state_value = s_value.apply(
                        x=embedding.get('state-embedding', embedding['embedding'])
                    )
                    advantage_value = a_value.apply(
                        x=embedding.get('action-embedding', embedding['embedding'])
                    )
                else:
                    state_value = s_value.apply(
                        x=embedding.get(name + '-state-embedding', embedding['embedding'])
                    )
                    advantage_value = a_value.apply(
                        x=embedding.get(name + '-embedding', embedding['embedding'])
                    )
                if spec.type == 'bool':
                    shape = (-1,) + spec.shape + (2,)
                elif spec.type == 'int':
                    shape = (-1,) + spec.shape + (spec.num_values,)
                advantage_value = tf.reshape(tensor=advantage_value, shape=shape)
                mean = tf.math.reduce_mean(input_tensor=advantage_value, axis=-1, keepdims=True)
                action_value = tf.expand_dims(input=state_value, axis=-1) + (advantage_value - mean)
                if spec.type == 'bool':
                    return tf.where(
                        condition=action, x=action_value[..., 0], y=action_value[..., 1]
                    )
                elif spec.type == 'int':
                    action = tf.expand_dims(input=action, axis=(spec.rank + 1))
                    action_value = tf.gather(
                        params=action_value, indices=action, batch_dims=(spec.rank + 1)
                    )
                    return tf.squeeze(input=action_value, axis=(spec.rank + 1))

            return self.actions_spec.fmap(
                function=function, cls=TensorDict, with_names=True,
                zip_values=(self.s_values, self.a_values, actions)
            )

    @tf_function(num_args=4)
    def state_values(self, *, states, horizons, internals, auxiliaries):
        deterministic = tf_util.constant(value=True, dtype='bool')
        embedding, _ = self.network.apply(
            x=states, horizons=horizons, internals=internals, deterministic=deterministic,
            independent=True
        )
        if not isinstance(embedding, TensorDict):
            embedding = TensorDict(embedding=embedding)

        if self.state_value_mode == 'implicit':

            def function(name, spec, a_value):
                if name is None:
                    x = embedding.get('action-embedding', embedding['embedding'])
                else:
                    x = embedding.get(name + '-embedding', embedding['embedding'])
                action_value = a_value.apply(x=x)
                if spec.type == 'bool':
                    shape = (-1,) + spec.shape + (2,)
                elif spec.type == 'int':
                    shape = (-1,) + spec.shape + (spec.num_values,)
                action_value = tf.reshape(tensor=action_value, shape=shape)
                if spec.type == 'bool':
                    return tf.math.maximum(x=action_value[..., 0], y=action_value[..., 1])
                elif spec.type == 'int':
                    if self.config.enable_int_action_masking:
                        mask = auxiliaries[name]['mask']
                        min_float = tf_util.get_dtype(type='float').min
                        min_float = tf.fill(dims=tf.shape(input=action_value), value=min_float)
                        action_value = tf.where(condition=mask, x=action_value, y=min_float)
                    return tf.math.reduce_max(input_tensor=action_value, axis=-1)

            return self.actions_spec.fmap(
                function=function, cls=TensorDict, with_names=True, zip_values=(self.a_values,)
            )

        elif self.state_value_mode == 'separate':
            state_value = self.s_value.apply(
                x=embedding.get('state-embedding', embedding['embedding'])
            )

            def function(name, spec, a_value):
                if name is None:
                    x = embedding.get('action-embedding', embedding['embedding'])
                else:
                    x = embedding.get(name + '-embedding', embedding['embedding'])
                advantage_value = a_value.apply(x=x)
                if spec.type == 'bool':
                    shape = (-1,) + spec.shape + (2,)
                elif spec.type == 'int':
                    shape = (-1,) + spec.shape + (spec.num_values,)
                advantage_value = tf.reshape(tensor=advantage_value, shape=shape)
                mean = tf.math.reduce_mean(input_tensor=advantage_value, axis=-1, keepdims=True)
                shape = (-1,) + tuple(1 for _ in range(spec.rank + 1))
                _state_value = tf.reshape(tensor=state_value, shape=shape)
                action_value = _state_value + (advantage_value - mean)
                if spec.type == 'bool':
                    return tf.math.maximum(x=action_value[..., 0], y=action_value[..., 1])
                elif spec.type == 'int':
                    if self.config.enable_int_action_masking:
                        mask = auxiliaries[name]['mask']
                        min_float = tf_util.get_dtype(type='float').min
                        min_float = tf.fill(dims=tf.shape(input=action_value), value=min_float)
                        action_value = tf.where(condition=mask, x=action_value, y=min_float)
                    return tf.math.reduce_max(input_tensor=action_value, axis=-1)

            return self.actions_spec.fmap(
                function=function, cls=TensorDict, with_names=True, zip_values=(self.a_values,)
            )

        elif self.state_value_mode == 'separate-per-action':

            def function(name, spec, s_value):
                if name is None:
                    x = embedding.get('state-embedding', embedding['embedding'])
                else:
                    x = embedding.get(name + '-state-embedding', embedding['embedding'])
                state_value = s_value.apply(x=x)
                if spec.type == 'bool':
                    shape = (-1,) + spec.shape
                elif spec.type == 'int':
                    shape = (-1,) + spec.shape
                return tf.reshape(tensor=state_value, shape=shape)

            return self.actions_spec.fmap(
                function=function, cls=TensorDict, zip_values=(self.s_values,)
            )
