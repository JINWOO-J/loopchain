import json
from pathlib import Path
from typing import List

import pytest

from loopchain import configure as conf
from loopchain.baseservice import ObjectManager, RestClient
from loopchain.channel.channel_property import ChannelProperty
from loopchain.channel.channel_service import ChannelService
from loopchain.peermanager.peer_loader import PeerLoader


class TestPeerLoader:
    CHANNEL_NAME = "icon_dex"
    TEST_GETREPS_RESPONSE = [
        {"address": "hxAddress0", "p2pEndpoint": "127.0.0.1:0"},
        {"address": "hxAddress1", "p2pEndpoint": "127.0.0.1:1"},
        {"address": "hxAddress2", "p2pEndpoint": "127.0.0.1:2"},
        {"address": "hxAddress3", "p2pEndpoint": "127.0.0.1:3"},
    ]

    @pytest.fixture
    def mocking_rs_client(self, mocker):
        rs_client = mocker.MagicMock(RestClient)
        rs_client.call = mocker.MagicMock(return_value=self.TEST_GETREPS_RESPONSE)

        channel_service = mocker.MagicMock(ChannelService)
        channel_service.rs_client = rs_client

        ObjectManager().channel_service = channel_service

        yield

        ObjectManager().channel_service = None

    @pytest.fixture
    def mocking_channel_name(self):
        ChannelProperty().name = self.CHANNEL_NAME

        yield

        ChannelProperty().name = None

    @pytest.fixture
    def channel_manage_data(self, tmp_path, mocking_channel_name):
        return {
            self.CHANNEL_NAME: {
                "peers": [
                    {
                        "id": "hx1111111111111111111111111111111111111111",
                        "peer_target": "111.111.111.111:7100",
                        "order": 1
                    },
                    {
                        "id": "hx2222222222222222222222222222222222222222",
                        "peer_target": "222.222.222.222:7200",
                        "order": 2
                    },
                    {
                        "id": "hx3333333333333333333333333333333333333333",
                        "peer_target": "333.333.333.333:7300",
                        "order": 3
                    },
                    {
                        "id": "hx4444444444444444444444444444444444444444",
                        "peer_target": "444.444.444.444:7400",
                        "order": 4
                    }
                ]
            }
        }

    @pytest.fixture
    def channel_manage_data_path(self, tmp_path, channel_manage_data, mocker) -> Path:
        path = tmp_path / "channel_manage_data.json"
        mocker.patch.object(conf, "CHANNEL_MANAGE_DATA_PATH", path)

        with open(path, "w") as f:
            json.dump(channel_manage_data, f)

        return path

    def test_load_with_no_file_and_no_rest(self, mocker):
        never_exist_path = "never_exist.json"
        mocker.patch.object(conf, "CHANNEL_MANAGE_DATA_PATH", never_exist_path)
        assert not Path(never_exist_path).exists()

        with pytest.raises(Exception):
            PeerLoader.load()

    def test_load_from_file_if_path_exists(self, channel_manage_data_path: Path):
        assert channel_manage_data_path.exists()
        with open(channel_manage_data_path) as f:
            channel_manage_data: dict = json.load(f)

        expected_peer_data = channel_manage_data[self.CHANNEL_NAME]["peers"]
        actual_peer_data: list = PeerLoader.load()

        for expected, actual in zip(expected_peer_data, actual_peer_data):
            assert expected["id"] == actual["id"]
            assert expected["peer_target"] == actual["p2pEndpoint"]

    def test_load_from_rest_call(self, mocking_rs_client, mocking_channel_name):
        peer_results: List[dict] = PeerLoader.load()

        for expected, actual in zip(self.TEST_GETREPS_RESPONSE, peer_results):
            assert actual["id"] == expected["address"]
            assert actual["p2pEndpoint"] == expected["p2pEndpoint"]

