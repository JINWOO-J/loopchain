# Copyright 2018 ICON Foundation
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

from earlgrey import *

from loopchain import utils as util
from loopchain.peer.state_borg import PeerState
from loopchain.utils.message_queue import StubCollection


class PeerInnerTask:
    """ FIXME : replace
    def __init__(self, peer_service: 'PeerService'):
        self._peer_service = peer_service
    """
    def __init__(self):
        self._peer_state = PeerState()

    @message_queue_task
    async def hello(self):
        return 'peer_hello'

    @message_queue_task
    async def get_channel_infos(self):
        return self._peer_state.channel_infos

    @message_queue_task
    async def get_node_info_detail(self):
        channels_info = self._peer_state.channel_infos

        return {
            'peer_port': self._peer_state.peer_port,
            'peer_target': self._peer_state.peer_target,
            'rest_target': self._peer_state.rest_target,
            'rs_target': self._peer_state.radio_station_target,
            'peer_id': self._peer_state.peer_id,
            'node_type': self._peer_state.node_type.value,
        }

    @message_queue_task
    async def get_node_key(self) -> bytes:
        return self._peer_state.node_key

    @message_queue_task
    async def stop_outer(self):
        """
        FIXME : deprecated?
        """
        import warnings
        warnings.warn("stop_outer is not support", DeprecationWarning)
        return "stop outer"

    @message_queue_task
    async def start_outer(self):
        """
        FIXME : deprecated?
        """
        import warnings
        warnings.warn("start_outer is not support", DeprecationWarning)
        return "start outer"

    @message_queue_task(type_=MessageQueueType.Worker)
    def update_status(self, channel, status: dict):
        for item in status:
            # util.logger.spam(f"peer_inner_service:update_status "
            #                  f"{item}:{status[item]}")
            try:
                self._peer_state.status_cache[channel][item] = status[item]
            except KeyError:
                logging.debug(f"peer_inner_service:not init channel({channel})")

    @message_queue_task(type_=MessageQueueType.Worker)
    async def stop(self, message):
        logging.info(f"peer_inner_service:stop")
        for stub in StubCollection().channel_stubs.values():
            await stub.async_task().stop(message)

        util.exit_and_msg(message)

    @message_queue_task
    async def change_node_type(self, node_type):
        await self._peer_state.change_node_type(node_type)


class PeerInnerService(MessageQueueService[PeerInnerTask]):
    TaskType = PeerInnerTask

    def _callback_connection_lost_callback(self, connection: RobustConnection):
        util.exit_and_msg("MQ Connection lost.")


class PeerInnerStub(MessageQueueStub[PeerInnerTask]):
    TaskType = PeerInnerTask

    def _callback_connection_lost_callback(self, connection: RobustConnection):
        util.exit_and_msg("MQ Connection lost.")
