import os

import pytest

from loopchain.blockchain.types import Hash32
from loopchain.blockchain.votes import v0_1a
from testcase.unittest.blockchain.votes.test_vote import _TestVoteBase


class TestBlockVote(_TestVoteBase):
    block_version = "0.1a"

    REP = pytest.REPS[0]

    @pytest.fixture
    def vote(self, block_vote_factory):
        return block_vote_factory(block_version=self.block_version, signer=self.SIGNER)

    @pytest.mark.parametrize("block_hash, expected_result", [
        (Hash32(os.urandom(Hash32.size)), True),
        (Hash32.empty(), False)
    ])
    def test_block_vote_result_equals_block_hash(self, block_vote_factory, block_hash, expected_result):
        block_vote: v0_1a.BlockVote = block_vote_factory(block_version=self.block_version, signer=self.SIGNER, block_hash=block_hash)

        assert block_vote.result() is expected_result

    @pytest.mark.xfail(reason="Wrong. Check func signature")
    def test_empty_vote(self):
        block_height = 0
        vote = v0_1a.BlockVote.empty(rep=self.REP, block_height=block_height)

        assert not vote.result()
