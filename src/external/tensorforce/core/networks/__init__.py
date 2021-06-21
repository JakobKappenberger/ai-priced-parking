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

from tensorforce.core.networks.network import Network, LayerbasedNetwork, LayeredNetwork

# Require Network/LayerbasedNetwork
from tensorforce.core.networks.auto import AutoNetwork
from tensorforce.core.networks.keras import KerasNetwork
from tensorforce.core.networks.preprocessor import Preprocessor


network_modules = dict(
    auto=AutoNetwork, custom=LayeredNetwork, default=LayeredNetwork, keras=KerasNetwork,
    layered=LayeredNetwork
)


__all__ = [
    'AutoNetwork', 'LayerbasedNetwork', 'KerasNetwork', 'LayeredNetwork', 'Network',
    'network_modules', 'Preprocessor'
]
