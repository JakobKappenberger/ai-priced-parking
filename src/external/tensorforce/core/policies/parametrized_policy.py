# Copyright 2021 Tensorforce Team. All Rights Reserved.
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
from tensorforce.core import network_modules, TensorsSpec, tf_function
from tensorforce.core.policies import BasePolicy


class ParametrizedPolicy(BasePolicy):
    """
    Base class for parametrized ("degenerate") policies.
    """

    # Network first
    def __init__(self, network='auto', *, inputs_spec, outputs=None):
        # Assumed to be secondary base class, so super() constructor has already been called
        assert hasattr(self, 'name')

        # Network
        if isinstance(network, tf.keras.Model) or (
            isinstance(network, type) and issubclass(network, tf.keras.Model)
        ):
            network = dict(type='keras', model=network)
        self.network = self.submodule(
            name='network', module=network, modules=network_modules, inputs_spec=inputs_spec,
            outputs=outputs
        )
        output_spec = self.network.output_spec()
        if isinstance(output_spec, TensorsSpec):
            for name, spec in output_spec.items():
                if spec.type != 'float':
                    raise TensorforceError.type(
                        name='ParametrizedPolicy', argument='network {} output'.format(name),
                        dtype=spec.type
                    )
        else:
            if output_spec.type != 'float':
                raise TensorforceError.type(
                    name='ParametrizedPolicy', argument='network output', dtype=output_spec.type
                )

    @property
    def internals_spec(self):
        return self.network.internals_spec

    def internals_init(self):
        return self.network.internals_init()

    def max_past_horizon(self, *, on_policy):
        return self.network.max_past_horizon(on_policy=on_policy)

    def get_savedmodel_trackables(self):
        trackables = dict()
        for variable in self.network.variables:
            assert variable.name not in trackables
            trackables[variable.name] = variable
        return trackables

    @tf_function(num_args=0)
    def past_horizon(self, *, on_policy):
        return self.network.past_horizon(on_policy=on_policy)

    @tf_function(num_args=5)
    def next_internals(self, *, states, horizons, internals, actions, deterministic, independent):
        _, internals = self.network.apply(
            x=states, horizons=horizons, internals=internals, deterministic=deterministic,
            independent=independent
        )

        return internals
