import json
import os
from app.utils.blockchain_handler import Blockchain, Block

CHAIN_FILE = "blockchain_data.json"


def load_blockchain() -> Blockchain:
    """
    Load blockchain from JSON file.
    If file doesn't exist, return a new blockchain.
    """
    if os.path.exists(CHAIN_FILE):
        with open(CHAIN_FILE, "r") as f:
            data = json.load(f)

        chain = Blockchain()
        chain.chain = []  # Reset auto-generated genesis block

        for block_data in data:
            block = Block(
                index=block_data["index"],
                timestamp=block_data["timestamp"],
                data=block_data["data"],
                previous_hash=block_data["previous_hash"],
            )
            chain.chain.append(block)

        return chain

    # No file found → return fresh blockchain
    return Blockchain()


def save_blockchain(chain: Blockchain):
    """
    Save entire blockchain to disk.
    """
    with open(CHAIN_FILE, "w") as f:
        json.dump([block.__dict__ for block in chain.chain], f, indent=4)
