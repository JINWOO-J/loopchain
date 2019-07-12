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
"""A module for restful API server of Radio station"""

import _ssl
import json
import logging
import ssl
from concurrent import futures
from typing import List

import grpc
from sanic import Sanic, response
from sanic.views import HTTPMethodView

from loopchain import configure as conf, utils
from loopchain.baseservice import PeerListData, PeerManager, PeerStatus, PeerInfo
from loopchain.baseservice.ca_service import CAService
from loopchain.components import SingletonMetaClass
from loopchain.p2p import message_code
from loopchain.p2p.grpc_helper.grpc_message import P2PMessage
from loopchain.p2p.p2p_service import P2PRadiostationService, PeerType
from loopchain.p2p.stub_manager import StubManager


def get_channel_name_from_args(args) -> str:
    return args.get('channel', conf.LOOPCHAIN_DEFAULT_CHANNEL)


class ServerComponents(metaclass=SingletonMetaClass):
    """
    rest server for radio station
    FIXME : change class name
    """

    def __init__(self):
        self.__app = Sanic(__name__)
        self.__app.config.KEEP_ALIVE = False
        self.__stub_to_rs_service: StubManager = None

        # SSL 적용 여부에 따라 context 생성 여부를 결정한다.
        if conf.REST_SSL_TYPE is conf.SSLAuthType.none:
            self.__ssl_context = None
        elif conf.REST_SSL_TYPE == conf.SSLAuthType.server_only:
            self.__ssl_context = (conf.DEFAULT_SSL_CERT_PATH, conf.DEFAULT_SSL_KEY_PATH)
        elif conf.REST_SSL_TYPE == conf.SSLAuthType.mutual:
            self.__ssl_context = ssl.SSLContext(_ssl.PROTOCOL_SSLv23)

            self.__ssl_context.verify_mode = ssl.CERT_REQUIRED
            self.__ssl_context.check_hostname = False

            self.__ssl_context.load_verify_locations(cafile=conf.DEFAULT_SSL_TRUST_CERT_PATH)
            self.__ssl_context.load_cert_chain(conf.DEFAULT_SSL_CERT_PATH, conf.DEFAULT_SSL_KEY_PATH)
        else:
            utils.exit_and_msg(
                f"REST_SSL_TYPE must be one of [0,1,2]. But now conf.REST_SSL_TYPE is {conf.REST_SSL_TYPE}")

        self._p2p_service = P2PRadiostationService()

    @property
    def app(self):
        return self.__app

    @property
    def stub(self):
        return self.__stub_to_rs_service

    @property
    def ssl_context(self):
        return self.__ssl_context

    def set_stub_port(self, port):
        target = conf.IP_LOCAL + ':' + str(port)
        self._p2p_service.add_client(target)
        self.__stub_to_rs_service = self._p2p_service.get_client(target)

    def set_resource(self):
        self.__app.add_route(Peer.as_view(), '/api/v1/peer/<request_type:string>')
        self.__app.add_route(Configuration.as_view(), '/api/v1/conf')
        self.__app.add_route(Certificate.as_view(), '/api/v1/cert/<request_type:string>/<certificate_type:string>')

    def get_peer_list(self, channel):
        return self.__stub_to_rs_service.call(
            "GetPeerList",
            P2PMessage.common_request(request="", group_id="all_group_id", channel=channel))

    def get_leader_peer(self, channel):
        return self.__stub_to_rs_service.call(
            "Request",
            P2PMessage.get_message(code=message_code.Request.peer_get_leader, channel=channel))

    def get_peer_status(self, peer_id, group_id, channel):
        return self.__stub_to_rs_service.call_in_times(
            "GetPeerStatus",
            P2PMessage.get_peer_id(peer_id=peer_id, group_id=group_id, channel=channel))

    def get_peer_status_async(self, peer_id, group_id, channel) -> grpc.Future:
        return self.__stub_to_rs_service.call_async(
            "GetPeerStatus",
            P2PMessage.get_peer_id(peer_id=peer_id, group_id=group_id, channel=channel))

    def get_configuration(self, conf_info):
        return self.__stub_to_rs_service.call(
            "Request",
            P2PMessage.get_message(code=message_code.Request.rs_get_configuration, meta=conf_info))

    def set_configuration(self, conf_info):
        return self.__stub_to_rs_service.call(
            "Request",
            P2PMessage.get_message(code=message_code.Request.rs_set_configuration, meta=conf_info))

    def response_simple_success(self):
        result = {
            'response_code': message_code.Response.success,
            'message': message_code.get_response_msg(message_code.Response.success)
        }
        return result

    def abort_if_url_doesnt_exist(self, request_type, type_list):
        result = {'response_code': message_code.Response.fail}
        if request_type not in type_list.values():
            result['message'] = "The resource doesn't exist"

        return result

    def ready(self):
        async def ready_tasks():
            from loopchain import loggers
            loggers.get_preset().update_logger()
            loggers.update_other_loggers()

            logging.debug('rest_server:initialize complete.')

        self.__app.add_task(ready_tasks())

    def serve(self, api_port):
        self.ready()
        self.__app.run(host='0.0.0.0', port=api_port, debug=False, ssl=self.ssl_context)


class Peer(HTTPMethodView):
    __REQUEST_TYPE = {
        'PEER_LIST': 'list',
        'LEADER_PEER': 'leader',
        'PEER_STATUS': 'status',
        'PEER_STATUS_LIST': 'status-list'
    }

    async def get(self, request, request_type):
        # args = ServerComponents().parser.parse_args()
        args = request.raw_args
        channel = get_channel_name_from_args(args)
        logging.debug(f'channel name : {channel}')
        if request_type == self.__REQUEST_TYPE['PEER_LIST']:
            grpc_response = ServerComponents().get_peer_list(channel)

            peer_manager = PeerManager(channel)
            peer_list_data = PeerListData.load(grpc_response.peer_list)
            peer_manager.set_peer_list(peer_list_data)

            all_peer_list = []
            connected_peer_list = []

            if peer_manager.peer_list:
                leader_peer_id = ""

                # for set peer_type info to peer
                leader_peer = peer_manager.get_leader_peer(is_peer=False)
                if leader_peer is not None:
                    leader_peer_id = leader_peer.peer_id

                for peer_id in peer_manager.peer_list:
                    peer_each: PeerInfo = peer_manager.peer_list[peer_id]
                    peer_data = peer_each.serialize()

                    if peer_each.peer_id == leader_peer_id:
                        peer_data['peer_type'] = PeerType.BLOCK_GENERATOR
                    else:
                        peer_data['peer_type'] = PeerType.PEER

                    all_peer_list.append(peer_data)

                    if peer_each.status == PeerStatus.connected:
                        connected_peer_list.append(peer_data)

            json_data = {
                'registered_peer_count': len(all_peer_list),
                'connected_peer_count': len(connected_peer_list),
                'registered_peer_list': all_peer_list,
                'connected_peer_list': connected_peer_list
            }
            result = {
                'response_code': message_code.Response.success,
                'data': json_data
            }
            
        elif request_type == self.__REQUEST_TYPE['PEER_STATUS_LIST']:
            grpc_response = ServerComponents().get_peer_list(channel)

            peer_manager = PeerManager(channel)
            peer_list_data = PeerListData.load(grpc_response.peer_list)
            peer_manager.set_peer_list(peer_list_data)

            registered_peer_count = 0
            connected_peer_count = 0
            all_peer_list = []

            if peer_manager.peer_list:
                async_futures: List[grpc.Future] = []
                for peer_id in peer_manager.peer_list:
                    async_future = ServerComponents().get_peer_status_async(peer_id, "all_group_id", channel)
                    async_futures.append(async_future)

                if async_futures:
                    futures.as_completed(async_futures)

                for async_future, peer_id in zip(async_futures, peer_manager.peer_list):
                    if async_future.exception():
                        logging.warning(f'RequestType({request_type}), exception({async_future.exception()})')
                        continue

                    grpc_response = async_future.result()
                    if grpc_response is not None and grpc_response.status != "":
                        peer_each = peer_manager.peer_list[peer_id]
                        status_json = json.loads(grpc_response.status)
                        status_json["order"] = peer_each.order
                        all_peer_list.append(status_json)

                registered_peer_count = peer_manager.get_peer_count()
                connected_peer_count = peer_manager.get_connected_peer_count()

            json_data = {
                'registered_peer_count': registered_peer_count,
                'connected_peer_count': connected_peer_count,
                'peer_status_list': all_peer_list
            }
            result = {
                'response_code': message_code.Response.success,
                'data': json_data
            }

        elif request_type == self.__REQUEST_TYPE['LEADER_PEER']:
            grpc_response = ServerComponents().get_leader_peer(channel)

            result = dict()
            result['response_code'] = grpc_response.code

            if grpc_response.code == message_code.Response.success:
                peer_info = PeerInfo.load(grpc_response.object)
                result['data'] = peer_info.serialize()
            else:
                result['message'] = message_code.get_response_msg(grpc_response.code)

        elif request_type == self.__REQUEST_TYPE['PEER_STATUS']:
            peer_id = args['peer_id']
            group_id = args['group_id']

            if peer_id is None or group_id is None:
                return self.__abort_if_arg_isnt_enough('peer_id, group_id')

            # logging.debug(f"try get_peer_status peer_id({peer_id}), group_id({group_id})")
            grpc_response = ServerComponents().get_peer_status(args['peer_id'], args['group_id'], channel)
            result = json.loads(grpc_response.status)

        else:
            return ServerComponents().abort_if_url_doesnt_exist(request_type, self.__REQUEST_TYPE)

        return response.json(result)

    def __abort_if_arg_isnt_enough(self, param_name):
        result = dict()
        result['response_code'] = message_code.Response.fail_validate_params
        result['message'] = \
            message_code.get_response_msg(result['response_code']) \
            + ". You must throw all of parameters : " + param_name
        return result


# FIXME : change class name
class Configuration(HTTPMethodView):
    async def get(self, request):
        # args = ServerComponents().parser.parse_args()
        args = request.raw_args

        if 'name' in args:
            json_data = {'name': args['name']}
            request_data = json.dumps(json_data)
        else:
            request_data = ''

        grpc_response = ServerComponents().get_configuration(request_data)
        result = {'response_code': grpc_response.code}
        if grpc_response.meta is not "":
            result['data'] = json.loads(grpc_response.meta)
        else:
            result['message'] = grpc_response.message

        return response.json(result)

    async def post(self, request):
        result = dict()
        request_data = request.json

        try:
            if request_data is None:
                result['response_code'] = message_code.Response.fail
                result['message'] = 'You must throw parameter of JSON when you call (/api/v1/conf) by post method.'

            else:
                grpc_response = ServerComponents().set_configuration(json.dumps(request_data))
                result = {
                    'response_code': grpc_response.code,
                    'message': message_code.get_response_msg(message_code.Response.success)
                }

        except ValueError as e:
            result['response_code'] = message_code.Response.fail
            result['message'] = str(e)

        return response.json(result)


class Certificate(HTTPMethodView):
    __REQUEST_TYPE = {
        'CERT_LIST': 'list',
        'ISSUE': 'issue'
    }

    __CERTIFICATE_TYPE = {
        'CA': 'ca',
        'PEER': 'peer'
    }

    _DEFAULT_PATH = "resources/testcerts/"
    _DEFAULT_COMMON_NAME = "Test CA"
    _DEFAULT_ORGANIZATION_UNIT = "DEV"
    _DEFAULT_ORGANIZATION = "THeLoop"
    _DEFAULT_COUNTRY = "kr"
    _DEFAULT_PERIOD = 5

    async def get(self, request, request_type, certificate_type):
        ca = CAService(self._DEFAULT_PATH, None)
        result = dict()

        if request_type == self.__REQUEST_TYPE['CERT_LIST']:
            if certificate_type == self.__CERTIFICATE_TYPE['CA']:
                certificate = ca.get_ca_certificate()
                result['response_code'] = message_code.Response.success
                result['data'] = ca.get_certificate_json(certificate)

            elif certificate_type == self.__CERTIFICATE_TYPE['PEER']:
                certificate = ca.get_peer_certificate_list()
                cert_json = []

                for cert_key in certificate:
                    cert_peer = ca.get_peer_certificate(cert_key)
                    cert_json.append(ca.get_certificate_json(cert_peer))

                result['response_code'] = message_code.Response.success
                result['data'] = cert_json

            else:
                return ServerComponents().abort_if_url_doesnt_exist(certificate_type, self.__CERTIFICATE_TYPE)

        elif request_type == self.__REQUEST_TYPE['ISSUE']:
            if certificate_type == self.__CERTIFICATE_TYPE['CA']:
                ca.generate_ca_cert(
                    cn=self._DEFAULT_COMMON_NAME,
                    ou=self._DEFAULT_ORGANIZATION_UNIT,
                    o=self._DEFAULT_ORGANIZATION,
                    expire_period=self._DEFAULT_PERIOD,
                    password=None
                )

                return ServerComponents().response_simple_success()

            elif certificate_type == self.__CERTIFICATE_TYPE['PEER']:
                if ca.is_secure is False:
                    return self.__abort_if_CA_certificate_loading_fails()

                else:
                    ca.generate_peer_cert(self._DEFAULT_COMMON_NAME, None)
                    return ServerComponents().response_simple_success()

            else:
                return ServerComponents().abort_if_url_doesnt_exist(certificate_type, self.__CERTIFICATE_TYPE)

        else:
            return ServerComponents().abort_if_url_doesnt_exist(request_type, self.__REQUEST_TYPE)

        return response.json(result)

    def __abort_if_CA_certificate_loading_fails(self):
        result = {
            'response_code': message_code.Response.fail,
            'message': 'Fail loading of CA certificate.'
        }
        return response.json(result)
