import pytest

from loopchain.blockchain.types import ExternalAddress
from loopchain.blockchain.votes import v0_1a
from testcase.unittest.blockchain.votes.test_vote import _TestVoteBase


class TestLeaderVote(_TestVoteBase):
    block_version = "0.1a"
    OLD_LEADER = pytest.REPS[1]
    NEW_LEADER = pytest.REPS[2]

    @pytest.fixture
    def vote(self, leader_vote_factory):
        return leader_vote_factory(
            block_version=self.block_version, signer=self.SIGNER, old_leader=self.OLD_LEADER, new_leader=self.NEW_LEADER
        )

    def test_leader_vote_result_equals_next_leader(self, leader_vote_factory):
        vote: v0_1a.LeaderVote = leader_vote_factory(
            block_version=self.block_version, signer=self.SIGNER, old_leader=self.OLD_LEADER, new_leader=self.NEW_LEADER
        )

        assert vote.result() == self.NEW_LEADER

    def test_empty_vote_sets_new_leader_as_empty_hash(self):
        rep_num = 0
        block_height = 0
        round_ = 0

        leader_vote = v0_1a.LeaderVote.empty(
            rep=self.REPS[rep_num], block_height=block_height, round_=round_, old_leader=self.REPS[rep_num]
        )
        assert leader_vote.new_leader == ExternalAddress.empty()
        assert leader_vote.result() == ExternalAddress.empty()
