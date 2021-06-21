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

from tensorforce.environments.environment import Environment, RemoteEnvironment

from tensorforce.environments.multiprocessing_environment import MultiprocessingEnvironment
from tensorforce.environments.socket_environment import SocketEnvironment

from tensorforce.environments.arcade_learning_environment import ArcadeLearningEnvironment
from tensorforce.environments.openai_gym import OpenAIGym
from tensorforce.environments.openai_retro import OpenAIRetro
from tensorforce.environments.open_sim import OpenSim
from tensorforce.environments.pygame_learning_environment import PyGameLearningEnvironment
from tensorforce.environments.vizdoom import ViZDoom
from tensorforce.environments.carla_environment import CARLAEnvironment

from tensorforce.environments.cartpole import CartPole


environments = dict(
    default=OpenAIGym,
    ale=ArcadeLearningEnvironment, arcade_learning_environment=ArcadeLearningEnvironment,
    custom_cartpole=CartPole,
    gym=OpenAIGym, openai_gym=OpenAIGym,
    retro=OpenAIRetro, openai_retro=OpenAIRetro,
    osim=OpenSim, open_sim=OpenSim,
    ple=PyGameLearningEnvironment, pygame_learning_environment=PyGameLearningEnvironment,
    vizdoom=ViZDoom,
    carla=CARLAEnvironment, carla_environment=CARLAEnvironment
)


__all__ = [
    'ArcadeLearningEnvironment', 'Environment', 'MazeExplorer', 'MultiprocessingEnvironment',
    'OpenAIGym', 'OpenAIRetro', 'OpenSim', 'PyGameLearningEnvironment', 'RemoteEnvironment',
    'SocketEnvironment', 'ViZDoom', 'CARLAEnvironment'
]
