import functools
import os
from typing import List, Callable

import pytest

from loopchain.blockchain.types import Hash32
from loopchain.blockchain.votes import v0_1a
from loopchain.blockchain.votes.votes import VoteDuplicateError
from loopchain.blockchain.votes.votes import Votes
from testcase.unittest.blockchain.votes.test_votes import _TestVotesBase


class TestBlockVotes_v0_1a(_TestVotesBase):
    block_version = "0.1a"
    BLOCK_HASH = Hash32(os.urandom(Hash32.size))
    VOTING_RATIO = 0.67
    VOTED_REP_COUNT = int(VOTING_RATIO * 100)

    @pytest.fixture
    def vote(self, block_vote_factory):
        return block_vote_factory(
            block_version=self.block_version,
            signer=self.SIGNER,
            block_hash=self.BLOCK_HASH
        )

    @pytest.fixture
    def votes(self, block_votes_factory):
        return block_votes_factory(
            block_version=self.block_version,
            reps=self.REPS,
            block_hash=self.BLOCK_HASH
        )

    @pytest.fixture
    def setup_votes_for_get_result(self, block_vote_factory, votes):
        def _(voted_rep_count: int, _block_vote_factory, _votes) -> Votes:
            for voter_num in range(voted_rep_count):
                block_vote: v0_1a.BlockVote = block_vote_factory(
                    block_version=self.block_version,
                    signer=self.SIGNERS[voter_num],
                    block_hash=self.BLOCK_HASH)
                votes.add_vote(block_vote)

            return votes

        return functools.partial(_, _block_vote_factory=block_vote_factory, _votes=votes)

    def test_get_result_returns_none_if_not_enough_votes(self, setup_votes_for_get_result):
        votes = setup_votes_for_get_result(self.VOTED_REP_COUNT - 1)

        assert votes.get_result() is None
        assert votes.is_completed() is False

    def test_get_result_returns_none_if_votes_enough_but_result_is_not(self, setup_votes_for_get_result, block_vote_factory):
        votes = setup_votes_for_get_result(self.VOTED_REP_COUNT - 1)

        block_vote: v0_1a.BlockVote = block_vote_factory(
            block_version=self.block_version,
            signer=self.SIGNERS[self.VOTED_REP_COUNT],
            block_hash=Hash32.empty()
        )
        votes.add_vote(block_vote)

        assert votes.get_result() is None
        assert votes.is_completed() is False

    def test_get_result_is_true_if_true_votes_ge_quorum(self, setup_votes_for_get_result):
        votes = setup_votes_for_get_result(self.VOTED_REP_COUNT)

        assert votes.get_result() is True
        assert votes.is_completed() is True

    def test_get_result_is_true_if_false_votes_ge_minimum_true_quorum(self, block_vote_factory, votes):
        failure_threshold_count = 100 - self.VOTED_REP_COUNT

        for voter_num in range(failure_threshold_count):
            block_vote: v0_1a.BlockVote = block_vote_factory(
                block_version=self.block_version,
                signer=self.SIGNERS[voter_num],
                block_hash=Hash32.empty()
            )
            votes.add_vote(block_vote)

        assert votes.get_result() is None
        assert votes.is_completed() is False

        block_vote: v0_1a.BlockVote = block_vote_factory(
            block_version=self.block_version,
            signer=self.SIGNERS[failure_threshold_count],
            block_hash=self.BLOCK_HASH
        )
        votes.add_vote(block_vote)

        assert votes.get_result() is None
        assert votes.is_completed() is False

        block_vote: v0_1a.BlockVote = block_vote_factory(
            block_version=self.block_version,
            signer=self.SIGNERS[failure_threshold_count+1],
            block_hash=Hash32.empty()
        )
        votes.add_vote(block_vote)

        assert votes.get_result() is False
        assert votes.is_completed() is True

    def test_verify_vote_already_added_but_changed_vote_raises_duplicate_err(self, block_vote_factory, votes):
        block_vote: v0_1a.BlockVote = block_vote_factory(block_version=self.block_version, signer=self.SIGNER, block_hash=self.BLOCK_HASH)
        votes.add_vote(block_vote)

        duplicated_vote = block_vote_factory(block_version=self.block_version, signer=self.SIGNER, block_hash=Hash32.empty())

        with pytest.raises(VoteDuplicateError, match="Duplicate voting"):
            votes.verify_vote(vote=duplicated_vote)

    def test_verify_vote_with_different_block_hash(self, vote, votes):
        vote_block_hash = Hash32(os.urandom(Hash32.size))
        assert not vote.block_hash == vote_block_hash

        object.__setattr__(vote, "block_hash", vote_block_hash)

        with pytest.raises(RuntimeError, match="Vote block_hash not match"):
            votes.verify_vote(vote)

    @pytest.fixture
    def setup_votes_for_test_get_majority(self, block_vote_factory, votes: Votes) -> Callable[..., Votes]:
        def _setup_votes_for_test_get_majority(voted_rep_count: int, _block_vote_factory, _votes: Votes) -> Votes:
            # Make up votes
            for voter_num in range(voted_rep_count):
                block_vote: v0_1a.BlockVote = block_vote_factory(block_version=self.block_version, signer=self.SIGNERS[voter_num], block_hash=self.BLOCK_HASH)
                votes.add_vote(block_vote)

            # Make down votes
            for voter_num in range(voted_rep_count, len(self.REPS)):
                block_vote: v0_1a.BlockVote = block_vote_factory(block_version=self.block_version, signer=self.SIGNERS[voter_num], block_hash=Hash32.empty())
                votes.add_vote(block_vote)

            return votes
        return functools.partial(_setup_votes_for_test_get_majority, _block_vote_factory=block_vote_factory, _votes=votes)

    def test_get_majority_most(self, setup_votes_for_test_get_majority):
        voted_rep_count = 66
        votes = setup_votes_for_test_get_majority(voted_rep_count)

        majority_list = votes.get_majority()
        highest_agreement_for_block, highest_voted_count = majority_list[0]

        assert highest_agreement_for_block is True
        assert highest_voted_count == voted_rep_count

    def test_get_majorty_second(self, setup_votes_for_test_get_majority):
        voted_rep_count = 66
        votes = setup_votes_for_test_get_majority(voted_rep_count)

        majority_list = votes.get_majority()
        highest_agreement_for_block, highest_voted_count = majority_list[0]
        second_agreement_for_block, second_voted_count = majority_list[1]

        assert highest_agreement_for_block is True
        assert second_agreement_for_block is False
        assert highest_voted_count == voted_rep_count
        assert second_voted_count == len(self.REPS) - voted_rep_count

    def test_serialize_votes(self, block_vote_factory, votes):
        voted_rep_count = 66
        assert voted_rep_count <= len(self.REPS)

        for voter_num in range(voted_rep_count):
            block_vote: v0_1a.BlockVote = block_vote_factory(block_version=self.block_version, signer=self.SIGNERS[voter_num], block_hash=self.BLOCK_HASH)
            votes.add_vote(block_vote)

        serialized_votes: List[dict] = v0_1a.BlockVotes.serialize_votes(votes=votes.votes)

        vote_num = [serialized_vote for serialized_vote in serialized_votes if serialized_vote]
        assert len(vote_num) == voted_rep_count

    def test_deserialize_votes(self, block_vote_factory, votes):
        voted_rep_count = 66
        assert voted_rep_count <= len(self.REPS)

        for voter_num in range(voted_rep_count):
            block_vote: v0_1a.BlockVote = block_vote_factory(block_version=self.block_version, signer=self.SIGNERS[voter_num], block_hash=self.BLOCK_HASH)
            votes.add_vote(block_vote)

        serialized_votes: List[dict] = votes.serialize_votes(votes=votes.votes)
        deserialized_votes: List[v0_1a.BlockVote] = votes.deserialize_votes(votes_data=serialized_votes)

        assert votes.votes == deserialized_votes

        restored_votes = v0_1a.BlockVotes(
            reps=self.REPS, voting_ratio=self.VOTING_RATIO, block_height=self.BLOCK_HEIGHT, round_=self.ROUND,
            block_hash=self.BLOCK_HASH, votes=votes.votes
        )
        assert votes == restored_votes
