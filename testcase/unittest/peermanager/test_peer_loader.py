import json
from pathlib import Path

import pytest

from loopchain import configure as conf
from loopchain.peermanager.peer_loader import PeerLoader
from loopchain.channel.channel_property import ChannelProperty


class TestPeerLoader:
    CHANNEL_NAME = "icon_dex"

    @pytest.fixture
    def mocking_channel_name(self):
        ChannelProperty().name = self.CHANNEL_NAME
        print(f"ChannelProperty().name: {ChannelProperty().name}")

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
        print("conf.CHANNEL_MANAGE_DATA_PATH: ", conf.CHANNEL_MANAGE_DATA_PATH)

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
