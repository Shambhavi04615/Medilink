import hashlib
import json
import time
from typing import List


class Block:
    """
    A single block in the blockchain.
    """

    def __init__(self, index: int, timestamp: float, data: dict, previous_hash: str):
        self.index = index
        self.timestamp = timestamp
        self.data = data
        self.previous_hash = previous_hash
        self.hash = self.compute_hash()

    def compute_hash(self) -> str:
        """
        Compute SHA-256 hash of block contents.
        """
        block_string = json.dumps({
            "index": self.index,
            "timestamp": self.timestamp,
            "data": self.data,
            "previous_hash": self.previous_hash
        }, sort_keys=True).encode()

        return hashlib.sha256(block_string).hexdigest()


class Blockchain:
    """
    Simple blockchain implementation used for medicine tracking.
    """

    def __init__(self):
        self.chain: List[Block] = []
        self.create_genesis_block()

    def create_genesis_block(self):
        """
        Create the first block in the blockchain.
        """
        genesis = Block(
            index=0,
            timestamp=time.time(),
            data={"message": "Genesis Block"},
            previous_hash="0"
        )
        self.chain.append(genesis)

    def get_last_block(self) -> Block:
        return self.chain[-1]

    def add_block(self, data: dict) -> Block:
        """
        Add a block containing medicine batch info.
        """
        prev = self.get_last_block()
        new_block = Block(
            index=len(self.chain),
            timestamp=time.time(),
            data=data,
            previous_hash=prev.hash
        )
        self.chain.append(new_block)
        return new_block

    def is_chain_valid(self) -> bool:
        """
        Validate blockchain integrity.
        """
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            prev = self.chain[i - 1]

            if current.hash != current.compute_hash():
                return False

            if current.previous_hash != prev.hash:
                return False

        return True
