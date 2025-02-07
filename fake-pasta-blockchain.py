"""
FakePastaBlockchain.py

This is a simulation/test implementation for generating sample PaSta blockchain data.
It creates a mock blockchain with artificial transactions, validations, and network states
to help visualize and test how the PaSta cryptocurrency system might work.

The simulation includes:
- Mock transactions between randomly generated addresses
- Validation requirements (3 validations needed per block)
- Network state tracking including storage and difficulty
- Mint/burn calculations based on transaction sizes
- Unix millisecond timestamps
- Network metadata tracking

Output files:
- blockchain.json: The main blockchain data
- addresses.json: State of all addresses including balances and capabilities
- metadata.json: Global network state and statistics

This is NOT a real blockchain implementation - it's purely for testing and visualization purposes.
"""

import json
import hashlib
from datetime import datetime, timedelta
import random
import time
from typing import Dict, List, Set

class FakePastaBlockchain:
    def __init__(self, num_addresses: int = 10, initial_balance: float = 100.0):
        # Generate addresses with initial balances and storage stats
        self.addresses = {
            hashlib.sha256(str(i).encode()).hexdigest()[:40]: {
                "balance": initial_balance,
                "validations_performed": 0,
                "storage_blocks": random.randint(100, 1000),  # Number of blocks stored
                "storage_size_gb": round(random.uniform(1, 10), 2),  # Storage in GB
                "validations_performed": 0
            }
            for i in range(num_addresses)
        }
        
        # Blockchain metadata
        self.metadata = {
            "total_supply": initial_balance * num_addresses,
            "mint_rate": 0.0001,  # Fixed small mint rate (0.01% of 1 unit)
            "average_transaction_size": 0,
            "total_transactions": 0,
            "network_storage": sum(addr["storage_size_gb"] for addr in self.addresses.values()),
            "network_difficulty": 3  # Base network difficulty
        }
        
        self.blockchain = []
        self.pending_blocks = []
        self.start_time = time.time() * 1000 - (30 * 24 * 60 * 60 * 1000)  # 30 days ago in milliseconds
        
        # Create genesis block
        genesis_block = {
            "index": 0,
            "transactions": [],
            "timestamp": int(self.start_time),
            "previous_hash": "0",
            "hash": hashlib.sha256("genesis".encode()).hexdigest(),
            "status": "confirmed",
            "validations_received": [],
            "validations_performed": [],
            "aggregations_performed": [],
            "mint_amount": 0,
            "burn_amount": 0,
            "network_state": {
                "total_supply": self.metadata["total_supply"],
                "network_difficulty": self.metadata["network_difficulty"],
                "total_network_storage": self.metadata["network_storage"],
                "average_transaction_size": self.metadata["average_transaction_size"]
            }
        }
        
        self.blockchain.append(genesis_block)
        
    def calculate_mint_amount(self, transaction_amount: float) -> float:
        """Calculate mint amount for the transaction"""
        # Fixed small mint rate for now
        mint_amount = 0.0001  # 0.01% of 1 unit
        return mint_amount
        
    def create_block(self, from_address: str, to_address: str, amount: float, day: int) -> dict:
        """Create a new block with validation requirements and mint/burn calculations"""
        timestamp = int(self.start_time + (day * 24 * 60 * 60 * 1000))
        
        mint_amount = self.calculate_mint_amount(amount)
        
        transaction = {
            "from_address": from_address,
            "to_address": to_address,
            "amount": amount,
            "timestamp": timestamp
        }
        
        # Update network state
        self.metadata["total_transactions"] += 1
        new_avg = ((self.metadata["average_transaction_size"] * 
                   (self.metadata["total_transactions"] - 1) + amount) / 
                   self.metadata["total_transactions"])
        self.metadata["average_transaction_size"] = round(new_avg, 8)
        
        block = {
            "index": len(self.blockchain) + len(self.pending_blocks),
            "transactions": [transaction],
            "timestamp": timestamp,
            "previous_hash": self.blockchain[-1]["hash"],
            "status": "pending",
            "validations_received": [],
            "validations_performed": [],
            "aggregations_performed": [],
            "mint_amount": mint_amount,

            "total_supply": self.metadata["total_supply"] + mint_amount,
            "network_difficulty": self.metadata["network_difficulty"]
        }
        
        # Calculate block hash
        block_string = json.dumps(block, sort_keys=True)
        block["hash"] = hashlib.sha256(block_string.encode()).hexdigest()
        
        return block
    
    def validate_block(self, block: dict, validator_address: str) -> bool:
        """Simulate block validation by a node"""
        if validator_address in block["validations_received"]:
            return False
            
        block["validations_received"].append(validator_address)
        self.addresses[validator_address]["validations_performed"] += 1
        
        if len(block["validations_received"]) >= 3:
            block["status"] = "confirmed"
            return True
            
        return False
    
    def generate_blockchain(self, num_blocks: int = 25) -> None:
        """Generate a sequence of blocks with validations"""
        address_list = list(self.addresses.keys())
        
        for i in range(num_blocks):
            from_address = random.choice(address_list)
            to_address = random.choice([addr for addr in address_list if addr != from_address])
            amount = round(random.uniform(1, 20), 2)
            
            new_block = self.create_block(from_address, to_address, amount, i)
            
            # Validate three random pending blocks
            pending_blocks = [b for b in self.pending_blocks if len(b["validations_received"]) < 3]
            for _ in range(min(3, len(pending_blocks))):
                block_to_validate = random.choice(pending_blocks)
                new_block["validations_performed"].append(block_to_validate["hash"])
            
            # Get validations for the new block
            validators = random.sample(address_list, 3)
            for validator in validators:
                self.validate_block(new_block, validator)
            
            if new_block["status"] == "confirmed":
                self.blockchain.append(new_block)
                self.metadata["total_supply"] += new_block["mint_amount"]
                self.addresses[from_address]["balance"] -= amount
                self.addresses[to_address]["balance"] += amount
            else:
                self.pending_blocks.append(new_block)
            
            # Process pending blocks
            still_pending = []
            for block in self.pending_blocks:
                if block["status"] == "confirmed":
                    self.blockchain.append(block)
                    self.metadata["total_supply"] += block["mint_amount"]
                    tx = block["transactions"][0]
                    self.addresses[tx["from_address"]]["balance"] -= tx["amount"]
                    self.addresses[tx["to_address"]]["balance"] += tx["amount"]
                else:
                    still_pending.append(block)
            self.pending_blocks = still_pending
    
    def save_to_files(self) -> None:
        """Save blockchain and address data to JSON files"""
        with open("blockchain.json", "w") as f:
            json.dump(self.blockchain, f, indent=2)
            
        with open("addresses.json", "w") as f:
            json.dump(self.addresses, f, indent=2)
            
        with open("metadata.json", "w") as f:
            json.dump(self.metadata, f, indent=2)
        
        print(f"Generated blockchain with {len(self.blockchain)} confirmed blocks (including genesis)")
        print(f"Pending blocks: {len(self.pending_blocks)}")
        print(f"Final total supply: {self.metadata['total_supply']}")

# Create and run simulation
if __name__ == "__main__":
    pasta = FakePastaBlockchain(num_addresses=10)
    pasta.generate_blockchain(num_blocks=25)
    pasta.save_to_files()