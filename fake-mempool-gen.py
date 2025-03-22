import json
import os
import time
import random
from typing import Dict, List
import ecdsa
import base58

class FakeMempoolGenerator:
    def __init__(self, num_transactions: int = 5):
        self.network_path = "C:\\PastaNetwork"
        self.num_transactions = num_transactions
        
        # Load existing blockchain and addresses
        self.blockchain = self.load_json("blockchain.json", [])
        self.addresses = self.load_json("addresses.json", {})
        
        if not self.blockchain or not self.addresses:
            raise ValueError("Blockchain or addresses not found. Please run fake-blockchain-gen.py first.")
    
    def load_json(self, filename: str, default):
        """Load JSON file from network path"""
        filepath = os.path.join(self.network_path, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                return json.load(f)
        return default
    
    def get_balance(self, address: str) -> float:
        """Calculate current balance for an address"""
        balance = 0
        for block in self.blockchain:
            if block["receiver"] == address:
                balance += block["amount"]
            if block["sender"] == address and block["sender"] != "genesis":
                balance -= block["amount"]
        return balance
    
    def sign_transaction(self, private_key_str: str, sender: str, receiver: str, 
                        amount: float, timestamp: float) -> str:
        """Sign transaction data with real private key"""
        private_key_bytes = base58.b58decode(private_key_str)
        signing_key = ecdsa.SigningKey.from_string(private_key_bytes, curve=ecdsa.SECP256k1)
        
        message = f"{sender}{receiver}{amount}{timestamp}"
        signature = signing_key.sign(message.encode())
        return base58.b58encode(signature).decode()
    
    def generate_mempool(self) -> List[Dict]:
        """Generate a list of pending transactions"""
        mempool = []
        address_list = list(self.addresses.keys())
        
        for _ in range(self.num_transactions):
            # Select random sender and receiver
            from_address = random.choice(address_list)
            to_address = random.choice([addr for addr in address_list if addr != from_address])
            
            # Get sender's current balance
            current_balance = self.get_balance(from_address)
            
            # Only create transaction if sender has sufficient balance
            if current_balance > 0:
                # Generate random amount between 0.1 and 50% of current balance
                amount = round(random.uniform(0.1, current_balance * 0.5), 2)
                timestamp = time.time()
                
                # Get sender's private key
                private_key = self.addresses[from_address]
                
                # Create transaction
                transaction = {
                    "sender": from_address,
                    "receiver": to_address,
                    "amount": amount,
                    "timestamp": timestamp,
                    "signature": self.sign_transaction(
                        private_key,
                        from_address,
                        to_address,
                        amount,
                        timestamp
                    )
                }
                
                mempool.append(transaction)
        
        return mempool
    
    def save_mempool(self, mempool: List[Dict]) -> None:
        """Save mempool to JSON file"""
        mempool_path = os.path.join(self.network_path, "mempool.json")
        with open(mempool_path, "w") as f:
            json.dump(mempool, f, indent=2)
        
        print(f"\nGenerated {len(mempool)} pending transactions")
        print(f"Mempool saved to {mempool_path}")
        print("\nSample transactions:")
        for tx in mempool[:3]:  # Show first 3 transactions
            print(f"From: {tx['sender'][:8]}...")
            print(f"To: {tx['receiver'][:8]}...")
            print(f"Amount: {tx['amount']}")
            print("---")

if __name__ == "__main__":
    # Generate 5 pending transactions by default
    generator = FakeMempoolGenerator(num_transactions=5)
    mempool = generator.generate_mempool()
    generator.save_mempool(mempool) 