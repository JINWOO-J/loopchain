import functools
from typing import List, Callable

import pytest

from loopchain.blockchain.types import ExternalAddress
from loopchain.blockchain.votes import v0_1a
from loopchain.blockchain.votes.votes import VoteDuplicateError
from loopchain.blockchain.votes.votes import Votes
from testcase.unittest.blockchain.votes.test_votes import _TestVotesBase


class TestLeaderVotes_v0_1a(_TestVotesBase):
    block_version = "0.1a"
    OLD_LEADER = pytest.REPS[1]
    NEW_LEADER = pytest.REPS[2]
    VOTING_RATIO = 0.51
    VOTED_REP_COUNT = int(VOTING_RATIO * 100)

    @pytest.fixture
    def vote(self, leader_vote_factory):
        return leader_vote_factory(
            block_version=self.block_version, signer=self.SIGNER, old_leader=self.OLD_LEADER, new_leader=self.NEW_LEADER
        )

    @pytest.fixture
    def votes(self, leader_votes_factory):
        return leader_votes_factory(
            block_version=self.block_version,
            reps=self.REPS,
            old_leader=self.OLD_LEADER,
            block_height=self.BLOCK_HEIGHT,
            round_=self.ROUND
        )

    @pytest.fixture
    def setup_votes_for_get_result(self, leader_vote_factory, votes) -> Callable[..., Votes]:
        def _(voted_rep_count: int, _leader_vote_factory, _votes) -> Votes:
            for voter_num in range(voted_rep_count):
                leader_vote: v0_1a.LeaderVote = leader_vote_factory(
                    block_version=self.block_version,
                    signer=self.SIGNERS[voter_num],
                    old_leader=self.OLD_LEADER,
                    new_leader=self.NEW_LEADER
                )
                votes.add_vote(leader_vote)
            return votes

        return functools.partial(_, _leader_vote_factory=leader_vote_factory, _votes=votes)

    def test_get_result_returns_none_if_not_enough_votes(self, setup_votes_for_get_result):
        votes = setup_votes_for_get_result(self.VOTED_REP_COUNT - 1)

        assert votes.get_result() is None
        assert votes.is_completed() is False

    def test_get_result_returns_new_leader_if_votes_enough(self, setup_votes_for_get_result):
        votes = setup_votes_for_get_result(self.VOTED_REP_COUNT)

        assert votes.get_result() is self.NEW_LEADER
        assert votes.is_completed() is True

    def test_get_result_returns_none_if_votes_enough_but_result_is_not(self, setup_votes_for_get_result, leader_vote_factory):
        votes = setup_votes_for_get_result(self.VOTED_REP_COUNT - 1)

        leader_vote: v0_1a.LeaderVote = leader_vote_factory(
            block_version=self.block_version,
            signer=self.SIGNERS[self.VOTED_REP_COUNT],
            old_leader=self.OLD_LEADER,
            new_leader=self.OLD_LEADER
        )
        votes.add_vote(leader_vote)

        assert votes.get_result() is None
        assert votes.is_completed() is False

    def test_get_result_counts_empty_vote_as_majority(self, setup_votes_for_get_result, leader_vote_factory):
        votes = setup_votes_for_get_result(self.VOTED_REP_COUNT - 1)

        leader_vote: v0_1a.LeaderVote = leader_vote_factory(
            block_version=self.block_version,
            signer=self.SIGNERS[self.VOTED_REP_COUNT],
            old_leader=self.OLD_LEADER,
            new_leader=ExternalAddress.empty()
        )
        votes.add_vote(leader_vote)

        assert votes.get_result() is self.NEW_LEADER
        assert votes.is_completed() is True

    def test_verify_vote_already_added_but_changed_vote_raises_duplicate_err(self, leader_vote_factory, votes):
        leader_vote: v0_1a.LeaderVote = leader_vote_factory(block_version=self.block_version, signer=self.SIGNER, old_leader=self.OLD_LEADER, new_leader=self.NEW_LEADER)
        votes.add_vote(leader_vote)

        duplicated_vote: v0_1a.LeaderVote = leader_vote_factory(block_version=self.block_version, signer=self.SIGNER, old_leader=self.OLD_LEADER, new_leader=self.OLD_LEADER)

        with pytest.raises(VoteDuplicateError, match="Duplicate voting"):
            votes.verify_vote(vote=duplicated_vote)

    def test_verify_vote_with_different_old_leader(self, vote, votes):
        assert not vote.old_leader == self.NEW_LEADER

        object.__setattr__(vote, "old_leader", self.NEW_LEADER)

        with pytest.raises(RuntimeError, match="Vote old_leader not match"):
            votes.verify_vote(vote=vote)

    @pytest.fixture
    def setup_votes_for_test_get_majority(self, leader_vote_factory, votes) -> Callable[..., Votes]:
        def _setup_votes_for_test_get_majority(voted_rep_count: int, _leader_vote_factory, _votes, second_leader=self.REPS[-1]) -> Votes:
            # Make up votes for NEW_LEADER
            for voter_num in range(voted_rep_count):
                leader_vote: v0_1a.LeaderVote = leader_vote_factory(
                    block_version=self.block_version,
                    signer=self.SIGNERS[voter_num],
                    old_leader=self.OLD_LEADER,
                    new_leader=self.NEW_LEADER
                )
                votes.add_vote(leader_vote)

            # Make up votes for second leader
            assert second_leader != self.NEW_LEADER

            for voter_num in range(voted_rep_count, len(self.REPS)):
                leader_vote: v0_1a.LeaderVote = leader_vote_factory(
                    block_version=self.block_version,
                    signer=self.SIGNERS[voter_num],
                    old_leader=self.OLD_LEADER,
                    new_leader=second_leader
                )
                votes.add_vote(leader_vote)

            return votes

        return functools.partial(
            _setup_votes_for_test_get_majority, _leader_vote_factory=leader_vote_factory, _votes=votes
        )

    def test_get_majority_most(self, setup_votes_for_test_get_majority):
        votes = setup_votes_for_test_get_majority(self.VOTED_REP_COUNT)
        majority_list = votes.get_majority()
        highest_voted_leader, highest_voted_count = majority_list[0]

        assert highest_voted_leader is self.NEW_LEADER
        assert highest_voted_count == self.VOTED_REP_COUNT

    def test_get_majority_second(self, setup_votes_for_test_get_majority):
        second_leader = self.REPS[-1]
        votes = setup_votes_for_test_get_majority(self.VOTED_REP_COUNT, second_leader=second_leader)
        majority_list = votes.get_majority()
        second_voted_leader, second_voted_count = majority_list[1]

        assert second_voted_leader == second_leader
        assert second_voted_count == len(self.REPS) - self.VOTED_REP_COUNT

    def test_serialize_votes(self, leader_vote_factory, votes):
        for voter_num in range(self.VOTED_REP_COUNT):
            leader_vote: v0_1a.LeaderVote = leader_vote_factory(
                block_version=self.block_version,
                signer=self.SIGNERS[voter_num],
                old_leader=self.OLD_LEADER,
                new_leader=self.NEW_LEADER
            )
            votes.add_vote(leader_vote)

        serialized_votes: List[dict] = v0_1a.LeaderVotes.serialize_votes(votes=votes.votes)
        vote_num = [serialized_vote for serialized_vote in serialized_votes if serialized_vote]

        assert len(vote_num) == self.VOTED_REP_COUNT

    @pytest.mark.xfail(reason="What is this method for?")
    def test_deserialize(self, leader_vote_factory, votes):
        for voter_num in range(len(self.REPS)):
            leader_vote: v0_1a.LeaderVote = leader_vote_factory(
                block_version=self.block_version,
                signer=self.SIGNERS[voter_num],
                old_leader=self.OLD_LEADER,
                new_leader=self.NEW_LEADER
            )
            votes.add_vote(leader_vote)

        serialized_votes: List[dict] = votes.serialize_votes(votes=votes.votes)
        deserialized_votes = votes.deserialize(votes_data=serialized_votes, voting_ratio=votes.voting_ratio)

        assert votes == deserialized_votes

    @pytest.mark.xfail(reason="What is this method for?")
    def test_deserialize_without_votes(self, votes):
        serialized_votes: List[dict] = votes.serialize_votes(votes=votes.votes)
        assert not all(serialized_votes)
        assert len(serialized_votes) == len(self.REPS)

        deserialized_votes = votes.deserialize(votes_data=serialized_votes, voting_ratio=votes.voting_ratio)

        assert votes == deserialized_votes

    def test_deserialize_votes(self, leader_vote_factory, votes):
        voted_rep_count = 51
        assert voted_rep_count <= len(self.REPS)

        for voter_num in range(voted_rep_count):
            leader_vote: v0_1a.LeaderVote = leader_vote_factory(
                block_version=self.block_version,
                signer=self.SIGNERS[voter_num],
                old_leader=self.OLD_LEADER,
                new_leader=self.NEW_LEADER
            )
            votes.add_vote(leader_vote)

        serialized_votes: List[dict] = votes.serialize_votes(votes=votes.votes)
        deserialized_votes: List[v0_1a.BlockVote] = votes.deserialize_votes(votes_data=serialized_votes)

        assert votes.votes == deserialized_votes

        restored_votes = v0_1a.LeaderVotes(
            reps=self.REPS, voting_ratio=self.VOTING_RATIO, block_height=self.BLOCK_HEIGHT, round_=self.ROUND,
            old_leader=self.OLD_LEADER, votes=votes.votes
        )

        assert votes == restored_votes
