from dataclasses import dataclass
from typing import List
from loopchain.crypto.hashing import build_hash_generator
from loopchain.blockchain.types import Hash32, ExternalAddress, BloomFilter
from loopchain.blockchain.blocks import BlockHeader as BaseBlockHeader, BlockBody as BaseBlockBody
from loopchain.blockchain.votes.v0_3 import BlockVote, LeaderVote


@dataclass(frozen=True)
class BlockHeader(BaseBlockHeader):
    next_leader: ExternalAddress

    bloom_filter: BloomFilter
    transaction_hash: Hash32
    state_hash: Hash32
    receipt_hash: Hash32
    rep_hash: Hash32
    leader_vote_hash: Hash32
    prev_vote_hash: Hash32

    version = "0.3"

    @property
    def complained(self):
        return self.leader_vote_hash != Hash32.empty()


@dataclass(frozen=True)
class BlockBody(BaseBlockBody):
    leader_votes: List[LeaderVote]
    prev_votes: List[BlockVote]


receipt_hash_generator = build_hash_generator(1, "icx_receipt")
