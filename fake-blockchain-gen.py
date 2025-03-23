import json
import hashlib
import random
import time
from typing import Dict, List
import ecdsa
import base58
import os

class FakePastaBlockchain:
    def __init__(self, num_addresses: int = 5, initial_balance: float = 1000.0):
        self.network_path = "C:\\PastaNetwork"
        if not os.path.exists(self.network_path):
            os.makedirs(self.network_path)
            
        # Generate keypairs and store addresses with initial balances
        self.addresses = {}
        self.keypairs = {}
        
        for i in range(num_addresses):
            private_key = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1)
            public_key = private_key.get_verifying_key()
            
            # Convert to base58 strings
            private_key_str = base58.b58encode(private_key.to_string()).decode()
            public_key_str = base58.b58encode(public_key.to_string()).decode()
            
            self.addresses[public_key_str] = initial_balance
            self.keypairs[public_key_str] = private_key_str
        
        self.blockchain = []
        self.start_time = time.time()
        
        # Create genesis block
        first_address = list(self.addresses.keys())[0]
        genesis_block = {
            "index": 0,
            "sender": "genesis",
            "receiver": first_address,
            "amount": initial_balance,
            "timestamp": int(self.start_time),
            "signature": "genesis_signature",
            "predecessor_index": None,
            "layer": 0,
            "sender_balance_before": 0,
            "sender_balance_after": 0,
            "receiver_balance_before": 0,
            "receiver_balance_after": initial_balance,
<<<<<<< HEAD
            "previous_hash": "0",
            "validating_block_id": None,
            "validating_block_subhash": None,
            "mintburn": 0.0
=======
            "previous_hash": "0"
>>>>>>> d95eb08e4bd8562ac4e11c5b197182ed5df72102
        }
        
        # Add genesis block hash
        genesis_block["hash"] = self.calculate_block_hash(genesis_block)
        
        self.blockchain.append(genesis_block)
        
    def get_balance(self, address: str) -> float:
        """Calculate current balance for an address"""
        balance = 0
        for block in self.blockchain:
            if block["receiver"] == address:
                balance += block["amount"]
            if block["sender"] == address and block["sender"] != "genesis":
                balance -= block["amount"]
        return balance

    def find_predecessor_and_layer(self) -> tuple:
        """Find appropriate predecessor and layer for new block"""
        if not self.blockchain:
            return None, 0
            
        # Get all blocks that are currently predecessors
        used_predecessors = {
            block.get("predecessor_index")
            for block in self.blockchain
            if block.get("predecessor_index") is not None
        }
        
        # Find available chain ends
        available_ends = []
        for i, block in enumerate(self.blockchain):
            if i not in used_predecessors:
                available_ends.append((i, block))
        
        if available_ends:
            # Sort by layer and use the lowest layer
            available_ends.sort(key=lambda x: x[1].get("layer", 0))
            return available_ends[0][0], available_ends[0][1].get("layer", 0)
        else:
            # Need to bifurcate - use most recent block
            latest_block = self.blockchain[-1]
            return len(self.blockchain) - 1, latest_block.get("layer", 0) + 1

    def sign_transaction(self, private_key_str: str, sender: str, receiver: str, 
                        amount: float, timestamp: float) -> str:
        """Sign transaction data with real private key"""
        private_key_bytes = base58.b58decode(private_key_str)
        signing_key = ecdsa.SigningKey.from_string(private_key_bytes, curve=ecdsa.SECP256k1)
        
        message = f"{sender}{receiver}{amount}{timestamp}"
        signature = signing_key.sign(message.encode())
        return base58.b58encode(signature).decode()

    def calculate_block_hash(self, block: dict) -> str:
        """Calculate hash of block including all its data"""
        # Create a copy of the block without the hash field
        block_for_hash = block.copy()
        if "hash" in block_for_hash:
            del block_for_hash["hash"]
            
        # Convert block to string and hash
        block_string = json.dumps(block_for_hash, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()

    def create_block(self, from_address: str, to_address: str, amount: float) -> dict:
        """Create a new block with real signature and hash"""
        predecessor_index, layer = self.find_predecessor_and_layer()
        timestamp = time.time()
        
        # Calculate balances
        sender_balance_before = self.get_balance(from_address)
        receiver_balance_before = self.get_balance(to_address)
        
        # Get real signature using sender's private key
        signature = self.sign_transaction(
            self.keypairs[from_address],
            from_address,
            to_address,
            amount,
            timestamp
        )
        
        # Get previous block's hash
        previous_hash = self.blockchain[-1]["hash"] if self.blockchain else "0"
        
<<<<<<< HEAD
        # Generate random mintburn value between 0 and 0.1
        mintburn = round(random.uniform(0, 0.1), 6)
        
        # For non-genesis blocks, set validating block to be the predecessor
        validating_block_id = predecessor_index if predecessor_index is not None else None
        validating_block_subhash = None
        
        if validating_block_id is not None:
            # Create a copy of the validating block without the hash field
            validating_block = self.blockchain[validating_block_id].copy()
            if "hash" in validating_block:
                del validating_block["hash"]
            # Calculate intermediate hash
            validating_block_subhash = hashlib.sha256(
                json.dumps(validating_block, sort_keys=True).encode()
            ).hexdigest()
        
=======
>>>>>>> d95eb08e4bd8562ac4e11c5b197182ed5df72102
        block = {
            "index": len(self.blockchain),
            "sender": from_address,
            "receiver": to_address,
            "amount": amount,
            "timestamp": timestamp,
            "signature": signature,
            "predecessor_index": predecessor_index,
            "layer": layer,
            "sender_balance_before": sender_balance_before,
            "sender_balance_after": sender_balance_before - amount,
            "receiver_balance_before": receiver_balance_before,
            "receiver_balance_after": receiver_balance_before + amount,
<<<<<<< HEAD
            "previous_hash": previous_hash,
            "validating_block_id": validating_block_id,
            "validating_block_subhash": validating_block_subhash,
            "mintburn": mintburn
=======
            "previous_hash": previous_hash
>>>>>>> d95eb08e4bd8562ac4e11c5b197182ed5df72102
        }
        
        # Calculate and add this block's hash
        block["hash"] = self.calculate_block_hash(block)
        
        return block
    
    def generate_blockchain(self, num_blocks: int = 20) -> None:
        """Generate a sequence of blocks"""
        address_list = list(self.addresses.keys())
        
        for _ in range(num_blocks):
            from_address = random.choice(address_list)
            to_address = random.choice([addr for addr in address_list if addr != from_address])
            
            # Only create transaction if sender has sufficient balance
            current_balance = self.get_balance(from_address)
            if current_balance > 0:
                amount = round(random.uniform(1, current_balance/2), 2)
                new_block = self.create_block(from_address, to_address, amount)
                self.blockchain.append(new_block)
    
    def save_to_files(self) -> None:
        """Save blockchain and address/keypair data to JSON files"""
        # Save blockchain
        blockchain_path = os.path.join(self.network_path, "blockchain.json")
        with open(blockchain_path, "w") as f:
            json.dump(self.blockchain, f, indent=2)
        
        # Save address list with keypairs
        addresses_path = os.path.join(self.network_path, "addresses.json")
        address_data = {
            public_key: private_key
            for public_key, private_key in self.keypairs.items()
        }
        with open(addresses_path, "w") as f:
            json.dump(address_data, f, indent=2)
        
        print(f"Generated blockchain with {len(self.blockchain)} blocks (including genesis)")
        print("\nAddresses generated:")
        for address in address_data.keys():
            print(f"{address[:8]}...")
        print(f"\nFull address data saved to {addresses_path}")

# Create and run simulation
if __name__ == "__main__":
    pasta = FakePastaBlockchain(num_addresses=5)
    pasta.generate_blockchain(num_blocks=20)
    pasta.save_to_files()