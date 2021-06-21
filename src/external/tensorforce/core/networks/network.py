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

from collections import Counter

import tensorflow as tf

from tensorforce import TensorforceError
from tensorforce.core import ArrayDict, Module, SignatureDict, TensorDict, TensorSpec, \
    TensorsSpec, tf_function, tf_util
from tensorforce.core.layers import Block, Layer, layer_modules, MultiInputLayer, \
    NondeterministicLayer, PreprocessingLayer, Register, Reuse, StatefulLayer, TemporalLayer
from tensorforce.core.parameters import Parameter


class Network(Module):
    """
    Base class for neural networks.

    Args:
        device (string): Device name
            (<span style="color:#00C000"><b>default</b></span>: inherit value of parent module).
        l2_regularization (float >= 0.0): Scalar controlling L2 regularization
            (<span style="color:#00C000"><b>default</b></span>: inherit value of parent module).
        name (string): <span style="color:#0000C0"><b>internal use</b></span>.
        inputs_spec (specification): <span style="color:#0000C0"><b>internal use</b></span>.
        outputs (iter[string]): <span style="color:#0000C0"><b>internal use</b></span>.
    """

    def __init__(
        self, *, device=None, l2_regularization=None, name=None, inputs_spec=None, outputs=None
    ):
        super().__init__(name=name, device=device, l2_regularization=l2_regularization)

        self.inputs_spec = inputs_spec

        if outputs is None:
            self.outputs = outputs
        else:
            self.outputs = tuple(outputs)
            if any(not isinstance(output, str) for output in self.outputs):
                raise TensorforceError.value(
                    name='LayerbasedNetwork', argument='outputs', value=self.outputs
                )

    def get_architecture(self):
        return self.__class__.__name__

    def output_spec(self):
        raise NotImplementedError

    @property
    def internals_spec(self):
        return TensorsSpec()

    def internals_init(self):
        return ArrayDict()

    def max_past_horizon(self, *, on_policy):
        return 0

    def input_signature(self, *, function):
        if function == 'apply':
            return SignatureDict(
                x=self.inputs_spec.signature(batched=True),
                horizons=TensorSpec(type='int', shape=(2,)).signature(batched=True),
                internals=self.internals_spec.signature(batched=True),
                deterministic=TensorSpec(type='bool', shape=()).signature(batched=False)
            )

        elif function == 'past_horizon':
            return SignatureDict()

        else:
            return super().input_signature(function=function)

    def output_signature(self, *, function):
        if function == 'apply':
            return SignatureDict(
                x=self.output_spec().signature(batched=True),
                internals=self.internals_spec.signature(batched=True)
            )

        elif function == 'past_horizon':
            return SignatureDict(
                singleton=TensorSpec(type='int', shape=()).signature(batched=False)
            )

        else:
            return super().output_signature(function=function)

    @tf_function(num_args=0)
    def past_horizon(self, *, on_policy):
        return tf_util.constant(value=0, dtype='int')

    @tf_function(num_args=4)
    def apply(self, *, x, horizons, internals, deterministic, independent):
        raise NotImplementedError


class LayerbasedNetwork(Network):
    """
    Base class for networks using Tensorforce layers.
    """

    def __init__(self, *, name, inputs_spec, device=None, l2_regularization=None, outputs=None):
        super().__init__(
            name=name, inputs_spec=inputs_spec, device=device, l2_regularization=l2_regularization
        )

        if self.inputs_spec.is_singleton():
            self.registered_tensors_spec = TensorsSpec(state=self.inputs_spec.singleton())
        else:
            self.registered_tensors_spec = self.inputs_spec.copy()

        self._output_spec = self.inputs_spec.value()

    def invalid_layer_types(self):
        return (PreprocessingLayer,)

    def output_spec(self):
        if self.outputs is None:
            return self._output_spec
        else:
            self.outputs = tuple(
                output for output in self.outputs if output in self.registered_tensors_spec
            )
            output_spec = TensorsSpec(embedding=self._output_spec)
            output_spec.update(self.registered_tensors_spec[self.outputs])
            return output_spec

    @staticmethod
    def _recursive_temporal_layers(*, layer, fn):
        if isinstance(layer, TemporalLayer):
            fn(layer)
        elif isinstance(layer, Block):
            for block_layer in layer.this_submodules:
                LayerbasedNetwork._recursive_temporal_layers(layer=block_layer, fn=fn)
        elif isinstance(layer, Reuse):
            LayerbasedNetwork._recursive_temporal_layers(layer=layer.reused_layer, fn=fn)

    @property
    def internals_spec(self):
        internals_spec = super().internals_spec

        def fn(layer):
            internals_spec[layer.name] = layer.internals_spec

        for layer in self.this_submodules:
            LayerbasedNetwork._recursive_temporal_layers(layer=layer, fn=fn)

        return internals_spec

    def internals_init(self):
        internals_init = super().internals_init()

        def fn(layer):
            internals_init[layer.name] = layer.internals_init()

        for layer in self.this_submodules:
            LayerbasedNetwork._recursive_temporal_layers(layer=layer, fn=fn)

        return internals_init

    def max_past_horizon(self, *, on_policy):
        past_horizons = [super().max_past_horizon(on_policy=on_policy)]

        def fn(layer):
            past_horizons.append(layer.max_past_horizon(on_policy=on_policy))

        for layer in self.this_submodules:
            LayerbasedNetwork._recursive_temporal_layers(layer=layer, fn=fn)

        return max(past_horizons)

    @tf_function(num_args=0)
    def past_horizon(self, *, on_policy):
        past_horizons = [super().past_horizon(on_policy=on_policy)]

        def fn(layer):
            past_horizons.append(layer.past_horizon(on_policy=on_policy))

        for layer in self.this_submodules:
            LayerbasedNetwork._recursive_temporal_layers(layer=layer, fn=fn)

        return tf.math.reduce_max(input_tensor=tf.stack(values=past_horizons, axis=0), axis=0)

    def submodule(
        self, *, name, module=None, modules=None, default_module=None, is_trainable=True,
        is_saved=True, **kwargs
    ):
        # Module class and args
        if modules is None:
            modules = layer_modules
        module_cls, args, kwargs = Module.get_module_class_and_args(
            name=name, module=module, modules=modules, default_module=default_module, **kwargs
        )
        if len(args) > 0:
            assert len(kwargs) == 0
            module_cls = args[0]

        # Default input_spec
        if not issubclass(module_cls, Layer):
            pass

        elif kwargs.get('input_spec') is None:
            if issubclass(module_cls, MultiInputLayer):
                if 'tensors' not in kwargs:
                    raise TensorforceError.required(name='MultiInputLayer', argument='tensors')
                tensors = kwargs['tensors']
                if isinstance(tensors, str):
                    tensors = (tensors,)
                else:
                    tensors = tuple(tensors)
                if tensors not in self.registered_tensors_spec:
                    raise TensorforceError.exists_not(
                        name='registered tensor', value=kwargs['tensors']
                    )
                kwargs['input_spec'] = self.registered_tensors_spec[tensors]

            elif self._output_spec is None:
                raise TensorforceError.required(
                    name='layer-based network', argument='first layer', expected='retrieve',
                    condition='multiple state/input components'
                )

            else:
                kwargs['input_spec'] = self._output_spec

        elif issubclass(module_cls, MultiInputLayer):
            raise TensorforceError.invalid(name='MultiInputLayer', argument='input_spec')

        layer = super().submodule(
            module=module_cls, modules=modules, default_module=default_module,
            is_trainable=is_trainable, is_saved=is_saved, **kwargs
        )

        if not isinstance(layer, (Layer, Parameter)):
            raise TensorforceError.type(
                name='layer-based network', argument='sub-module', value=layer
            )

        elif isinstance(layer, self.invalid_layer_types()):
            raise TensorforceError.type(
                name='network', argument='layer', value=layer, hint='invalid layer type'
            )

        if isinstance(layer, Layer):
            self._output_spec = layer.output_spec()

            if isinstance(layer, Register):
                if layer.tensor in self.registered_tensors_spec:
                    raise TensorforceError.exists(name='registered tensor', value=layer.tensor)
                self.registered_tensors_spec[layer.tensor] = layer.output_spec()

        return layer


class LayeredNetwork(LayerbasedNetwork):
    """
    Network consisting of Tensorforce layers (specification key: `custom` or `layered`), which can
    be specified as either a list of layer specifications in the case of a standard sequential
    layer-stack architecture, or as a list of list of layer specifications in the case of a more
    complex architecture consisting of multiple sequential layer-stacks. Note that the final
    action/value layer of the policy/baseline network is implicitly added, so the network output can
    be of arbitrary size and use any activation function, and is only required to be a rank-one
    embedding vector, or optionally have the same shape as the action in the case of a higher-rank
    action shape.

    Args:
        layers (iter[specification] | iter[iter[specification]]): Layers configuration, see the
            [layers documentation](../modules/layers.html)
            (<span style="color:#C00000"><b>required</b></span>).
        device (string): Device name
            (<span style="color:#00C000"><b>default</b></span>: inherit value of parent module).
        l2_regularization (float >= 0.0): Scalar controlling L2 regularization
            (<span style="color:#00C000"><b>default</b></span>: inherit value of parent module).
        name (string): <span style="color:#0000C0"><b>internal use</b></span>.
        inputs_spec (specification): <span style="color:#0000C0"><b>internal use</b></span>.
        outputs (iter[string]): <span style="color:#0000C0"><b>internal use</b></span>.
    """

    # (requires layers as first argument)
    def __init__(
        self, layers, *, device=None, l2_regularization=None, name=None, inputs_spec=None,
        outputs=None
    ):
        super().__init__(
            device=device, l2_regularization=l2_regularization, name=name, inputs_spec=inputs_spec,
            outputs=outputs
        )

        self.layers = self._parse_layers_spec(spec=layers, counter=Counter())

    def get_architecture(self):
        architecture = LayeredNetwork._recursive_get_architecture(layer=self.layers)
        while '----\n----' in architecture:
            architecture = architecture.replace('----\n----', '----')
        if architecture.startswith('----'):
            architecture = architecture[4:]
        return architecture

    @staticmethod
    def _recursive_get_architecture(*, layer):
        if isinstance(layer, list):
            return '----\n' + '\n'.join(
                LayeredNetwork._recursive_get_architecture(layer=layer) for layer in layer
            )

        else:
            return layer.get_architecture()

    def _parse_layers_spec(self, *, spec, counter):
        if isinstance(spec, list):
            return [self._parse_layers_spec(spec=s, counter=counter) for s in spec]

        else:
            if callable(spec):
                spec = dict(type='function', function=spec)
            elif isinstance(spec, str):
                spec = dict(type=spec)

            # Deprecated
            if spec.get('type') in ('internal_rnn', 'internal_lstm', 'internal_gru'):
                raise TensorforceError.deprecated(
                    name='Network layers', argument=spec['type'], replacement=spec['type'][9:]
                )

            if 'name' in spec:
                spec = dict(spec)
                name = spec.pop('name')

            else:
                layer_type = spec.get('type')
                if not isinstance(layer_type, str):
                    layer_type = 'layer'
                name = layer_type + str(counter[layer_type])
                counter[layer_type] += 1

            return self.submodule(name=name, module=spec)

    @tf_function(num_args=4)
    def apply(self, *, x, horizons, internals, deterministic, independent):
        if x.is_singleton():
            registered_tensors = TensorDict(state=x.singleton())
        else:
            registered_tensors = x.copy()
        x = x.value()

        temporal_layer_check = False
        x, _ = LayeredNetwork._recursive_apply(
            layer=self.layers, x=x, horizons=horizons, internals=internals,
            deterministic=deterministic, independent=independent,
            registered_tensors=registered_tensors, temporal_layer_check=temporal_layer_check
        )

        if self.outputs is not None:
            x = TensorDict(embedding=x)
            x.update(((output, registered_tensors[output]) for output in self.outputs))

        return x, internals

    @staticmethod
    def _recursive_apply(
        *, layer, x, horizons, internals, deterministic, independent, registered_tensors,
        temporal_layer_check
    ):
        if isinstance(layer, list):
            for layer in layer:
                x, temporal_layer_check = LayeredNetwork._recursive_apply(
                    layer=layer, x=x, horizons=horizons, internals=internals,
                    deterministic=deterministic, independent=independent,
                    registered_tensors=registered_tensors,
                    temporal_layer_check=temporal_layer_check
                )

        elif isinstance(layer, Block):
            for layer in layer.layers:
                x, temporal_layer_check = LayeredNetwork._recursive_apply(
                    layer=layer, x=x, horizons=horizons, internals=internals,
                    deterministic=deterministic, independent=independent,
                    registered_tensors=registered_tensors,
                    temporal_layer_check=temporal_layer_check
                )

        elif isinstance(layer, Reuse):
            x, temporal_layer_check = LayeredNetwork._recursive_apply(
                layer=layer.reused_layer, x=x, horizons=horizons, internals=internals,
                deterministic=deterministic, independent=independent,
                registered_tensors=registered_tensors,
                temporal_layer_check=temporal_layer_check
            )

        elif isinstance(layer, Register):
            if layer.tensor in registered_tensors:
                raise TensorforceError.exists(name='registered tensor', value=layer.tensor)
            x = layer.apply(x=x)
            registered_tensors[layer.tensor] = x

        elif isinstance(layer, MultiInputLayer):
            if layer.tensors not in registered_tensors:
                raise TensorforceError.exists_not(name='registered tensor', value=layer.tensors)
            x = layer.apply(x=registered_tensors[layer.tensors])
            temporal_layer_check = False

        elif isinstance(layer, NondeterministicLayer):
            x = layer.apply(x=x, deterministic=deterministic)

        elif isinstance(layer, StatefulLayer):
            x = layer.apply(x=x, independent=independent)

        elif isinstance(layer, TemporalLayer):
            if temporal_layer_check:
                raise TensorforceError(
                    "Multiple successive temporal layers like RNNs are currently not supported."
                )
            x, internals[layer.name] = layer.apply(
                x=x, horizons=horizons, internals=internals[layer.name]
            )
            temporal_layer_check = True

        else:
            x = layer.apply(x=x)

        return x, temporal_layer_check
