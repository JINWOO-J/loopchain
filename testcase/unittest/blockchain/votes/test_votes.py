import pytest

from loopchain.blockchain.types import ExternalAddress, Signature
from loopchain.blockchain.votes import v0_1a
from loopchain.blockchain.votes.votes import Vote, Votes
from loopchain.blockchain.votes.votes import VoteSafeDuplicateError, VoteNoRightRep
from loopchain.crypto.signature import Signer


@pytest.mark.parametrize("version_name", ["v0_3", "v0_4"])
def test_votes_v0_1a_equals_to(version_name: str):
    import importlib
    from loopchain.blockchain import votes

    vote_version = importlib.import_module(f"{votes.__name__}.{version_name}")

    assert v0_1a.BlockVotes == vote_version.BlockVotes
    assert v0_1a.LeaderVotes == vote_version.LeaderVotes


class _TestVotesBase:
    SIGNERS = pytest.SIGNERS
    SIGNER = SIGNERS[0]
    REPS = pytest.REPS
    VOTING_RATIO = 0.67
    BLOCK_HEIGHT = 0
    ROUND = 0

    @pytest.fixture
    def vote(self, override_vote_factory):
        pass

    @pytest.fixture
    def votes(self, override_votes_factory):
        pass

    def test_add_vote(self, vote: Vote, votes: Votes):
        votes.add_vote(vote=vote)

    def test_vote_safe_duplicate_error_is_acceptable_in_add_vote(self, vote: Vote, votes: Votes, mocker):
        votes.verify_vote = mocker.MagicMock(side_effect=VoteSafeDuplicateError)

        votes.add_vote(vote=vote)
        assert votes.verify_vote.called

    def test_verify(self, vote: Vote, votes: Votes):
        votes.add_vote(vote=vote)
        votes.verify()

    def test_verify_raises_if_vote_rep_not_equals_votes_rep(self, vote: Vote, votes: Votes):
        votes.add_vote(vote=vote)
        assert self.REPS[0] != self.REPS[1]
        assert self.REPS[0] == vote.rep == votes.reps[0]

        object.__setattr__(vote, "rep", self.REPS[1])

        with pytest.raises(RuntimeError, match="Incorrect Rep"):
            votes.verify()

    def test_verify_vote(self, vote: Vote, votes: Votes):
        votes.verify_vote(vote=vote)

    def test_verify_vote_with_different_height(self, vote: Vote, votes: Votes):
        object.__setattr__(vote, "block_height", 0)
        object.__setattr__(votes, "block_height", 1)

        with pytest.raises(RuntimeError, match="block_height not match"):
            votes.verify_vote(vote=vote)

    def test_verify_vote_with_different_round(self, vote: Vote, votes: Votes):
        object.__setattr__(vote, "round_", 0)
        object.__setattr__(votes, "round", 1)

        with pytest.raises(RuntimeError, match="Vote round not match"):
            votes.verify_vote(vote=vote)

    def test_verify_vote_with_already_added_vote(self, vote: Vote, votes: Votes):
        votes.add_vote(vote)

        with pytest.raises(VoteSafeDuplicateError):
            votes.verify_vote(vote=vote)

    def test_verify_vote_from_invalid_rep_raises_no_right_rep(self, vote: Vote, votes: Votes):
        signer = Signer.new()
        assert signer != self.SIGNER
        assert signer not in self.SIGNERS

        rep_id: ExternalAddress = ExternalAddress.fromhex(signer.address)
        object.__setattr__(vote, "rep", rep_id)

        hash_ = vote.to_hash(**vote.origin_args())
        signature = Signature(signer.sign_hash(hash_))
        object.__setattr__(vote, "signature", signature)

        with pytest.raises(VoteNoRightRep, match="no right to vote"):
            votes.verify_vote(vote=vote)

    def test_get_summary(self, vote: Vote, votes: Votes):
        assert votes.get_summary()

        votes.add_vote(vote)
        assert votes.get_summary()
