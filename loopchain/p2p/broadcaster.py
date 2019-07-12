# Copyright 2019 ICON Foundation
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

""" P2P Broadcaster """

import logging
import queue
from functools import partial

from loopchain import configure as conf
from loopchain.p2p.protos import loopchain_pb2_grpc, loopchain_pb2
from loopchain.p2p.stub_manager import StubManager


class Broadcaster:
    """broadcast class for each channel
    TODO : refactoring overall
    """

    def __init__(self, channel: str, self_target: str=None):
        self.__channel = channel
        self.__self_target = self_target

        self.__audience = {}  # self.__audience[peer_target] = stub_manager

        if conf.IS_BROADCAST_ASYNC:
            self.__broadcast_run = self.__broadcast_run_async
        else:
            self.__broadcast_run = self.__broadcast_run_sync

        self.__broadcast_with_self_target_methods = {
            "AddTx",
            "AddTxList",
            "BroadcastVote"
        }

        self.stored_tx = queue.Queue()

    def __broadcast_retry_async(self, peer_target, method_name, method_param,
                                retry_times, timeout, stub, result, exception):
        logging.debug(f"try retry to : peer_target({peer_target})\n")
        if retry_times > 0:
            try:
                stub_manager: StubManager = self.__audience[peer_target]
                if stub_manager is None:
                    logging.warning(f"broadcast_thread:__broadcast_retry_async Failed to connect to ({peer_target}).")
                    return
                retry_times -= 1
                is_stub_reuse = stub_manager.is_stub_reuse(stub, result, timeout)
                self.__call_async_to_target(peer_target, method_name, method_param, is_stub_reuse, retry_times, timeout)
            except KeyError as e:
                logging.debug(f"broadcast_thread:__broadcast_retry_async ({peer_target}) not in audience. ({e})")
        else:
            logging.warning(f"__broadcast_run_async fail({result})\n"
                            f"cause by: {exception}\n"
                            f"peer_target({peer_target})\n"
                            f"method_name({method_name})\n"
                            f"retry_remains({retry_times})\n"
                            f"timeout({timeout})")

    def __call_async_to_target(self, peer_target, method_name, method_param, is_stub_reuse, retry_times, timeout):
        try:
            stub_manager: StubManager = self.__audience[peer_target]
            if stub_manager is None:
                logging.debug(f"broadcast_thread:__call_async_to_target Failed to connect to ({peer_target}).")
                return
            call_back_partial = partial(self.__broadcast_retry_async,
                                        peer_target,
                                        method_name,
                                        method_param,
                                        retry_times,
                                        timeout,
                                        stub_manager.stub)
            stub_manager.call_async(method_name=method_name,
                                    message=method_param,
                                    is_stub_reuse=is_stub_reuse,
                                    call_back=call_back_partial,
                                    timeout=timeout)
        except KeyError as e:
            logging.debug(f"broadcast_thread:__call_async_to_target ({peer_target}) not in audience. ({e})")

    def __broadcast_run_async(self, method_name, method_param, retry_times=None, timeout=None):
        """call gRPC interface of audience

        :param method_name: gRPC interface
        :param method_param: gRPC message
        """

        if timeout is None:
            timeout = conf.GRPC_TIMEOUT_BROADCAST_RETRY

        retry_times = conf.BROADCAST_RETRY_TIMES if retry_times is None else retry_times
        # logging.debug(f"broadcast({method_name}) async... ({len(self.__audience)})")

        for target in self.__get_broadcast_targets(method_name):
            # utils.logger.debug(f"method_name({method_name}), peer_target({target})")
            self.__call_async_to_target(target, method_name, method_param, True, retry_times, timeout)

    def __broadcast_run_sync(self, method_name, method_param, retry_times=None, timeout=None):
        """call gRPC interface of audience

        :param method_name: gRPC interface
        :param method_param: gRPC message
        """
        # logging.debug(f"broadcast({method_name}) sync... ({len(self.__audience)})")

        if timeout is None:
            timeout = conf.GRPC_TIMEOUT_BROADCAST_RETRY

        retry_times = conf.BROADCAST_RETRY_TIMES if retry_times is None else retry_times

        for target in self.__get_broadcast_targets(method_name):
            try:
                stub_manager: StubManager = self.__audience[target]
                if stub_manager is None:
                    logging.debug(f"broadcast_thread:__broadcast_run_sync Failed to connect to ({target}).")
                    continue

                response = stub_manager.call_in_times(method_name=method_name,
                                                      message=method_param,
                                                      timeout=timeout,
                                                      retry_times=retry_times)
                if response is None:
                    logging.warning(f"broadcast_thread:__broadcast_run_sync fail ({method_name}) "
                                    f"target({target}) ")
            except KeyError as e:
                logging.debug(f"broadcast_thread:__broadcast_run_sync ({target}) not in audience. ({e})")

    def subscribe(self, audience_target):
        logging.warning("BroadcastThread received subscribe command peer_target: " + str(audience_target))
        if audience_target not in self.__audience:
            stub_manager = StubManager.get_stub_manager_to_server(
                audience_target, loopchain_pb2_grpc.PeerServiceStub,
                time_out_seconds=conf.CONNECTION_RETRY_TIMEOUT_WHEN_INITIAL,
                is_allow_null_stub=True,
                ssl_auth_type=conf.GRPC_SSL_TYPE
            )
            self.__audience[audience_target] = stub_manager

        # p2p_service.subscribe(audience_target)

    def unsubscribe(self, audience_target):
        # logging.debug(f"BroadcastThread received unsubscribe command peer_target({unsubscribe_peer_target})")
        try:
            del self.__audience[audience_target]
        except KeyError:
            logging.warning(f"Already deleted peer: {audience_target}")

        # p2p_service.unsubscribe(audience_target)

    def __handler_broadcast(self, broadcast_param):
        # logging.debug("BroadcastThread received broadcast command")
        broadcast_method_name = broadcast_param[0]
        broadcast_method_param = broadcast_param[1]
        broadcast_method_kwparam = broadcast_param[2]
        # logging.debug("BroadcastThread method name: " + broadcast_method_name)
        # logging.debug("BroadcastThread method param: " + str(broadcast_method_param))
        self.__broadcast_run(broadcast_method_name, broadcast_method_param, **broadcast_method_kwparam)

    def make_tx_list_message(self):
        tx_list = []
        tx_list_size = 0
        tx_list_count = 0
        remains = False
        while not self.stored_tx.empty():
            stored_tx_item = self.stored_tx.get()
            tx_list_size += len(stored_tx_item)
            tx_list_count += 1
            if tx_list_size >= conf.MAX_TX_SIZE_IN_BLOCK or tx_list_count >= conf.MAX_TX_COUNT_IN_ADDTX_LIST:
                self.stored_tx.put(stored_tx_item)
                remains = True
                break
            tx_list.append(stored_tx_item.get_tx_message())
        message = loopchain_pb2.TxSendList(
            channel=self.__channel,
            tx_list=tx_list
        )

        return remains, message

    def add_tx_item(self, tx_item):
        self.stored_tx.put(tx_item)

    def __get_broadcast_targets(self, method_name):
        """
        :param method_name:
        :return:
        """

        peer_targets = list(self.__audience)

        # TODO : remove ObjectManager
        from loopchain.baseservice.object_manager import ObjectManager
        if ObjectManager().rs_service:
            return peer_targets
        else:
            if self.__self_target is not None and method_name not in self.__broadcast_with_self_target_methods:
                peer_targets.remove(self.__self_target)
            return peer_targets

    def broadcast(self, broadcast_method_name, broadcast_method_param, kwargs=None):
        if kwargs is None:
            kwargs = {}
        self.__broadcast_run(broadcast_method_name, broadcast_method_param, **kwargs)

    def send_tx_list(self):
        remains, message = self.make_tx_list_message()
        self.broadcast("AddTxList", message)

        return remains
