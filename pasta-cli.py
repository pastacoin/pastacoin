import json
import os
import time
import hashlib
import ecdsa
import base58
import random
from typing import Optional, List, Dict, Tuple

NETWORK_PATH = "C:\\PastaNetwork"

def ensure_network_dirs():
    """Ensure network directories exist"""
    if not os.path.exists(NETWORK_PATH):
        os.makedirs(NETWORK_PATH)

def load_json(filename: str, default):
    filepath = os.path.join(NETWORK_PATH, filename)
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return default

def save_json(filename: str, data):
    filepath = os.path.join(NETWORK_PATH, filename)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

def get_balance(address: str, blockchain: List[Dict]) -> float:
    """Calculate balance for an address from blockchain"""
    balance = 0
    for block in blockchain:
        if block["receiver"] == address:
            balance += block["amount"]
        if block["sender"] == address:
            balance -= block["amount"]
    return balance

def find_chain_ends(blockchain: List[Dict], mempool: List[Dict]) -> List[Dict]:
    """Find all blocks that have no successors"""
    # Create set of all predecessor_indices
    used_predecessors = {
        block.get("predecessor_index") 
        for block in blockchain + mempool 
        if block.get("predecessor_index") is not None
    }
    
    # Find blocks that aren't predecessors to any other blocks
    ends = [
        block for i, block in enumerate(blockchain)
        if i not in used_predecessors
    ]
    
    return ends

def find_available_end(blockchain: List[Dict], mempool: List[Dict]) -> Optional[Dict]:
    """Find an available chain end that isn't taken by mempool transactions"""
    chain_ends = find_chain_ends(blockchain, [])
    if not chain_ends:
        return None
        
    # Sort ends by layer (prefer lower layers)
    chain_ends.sort(key=lambda x: x.get("layer", 0))
    
    # Check each end to see if it's already taken in mempool
    for end in chain_ends:
        end_index = blockchain.index(end)
        taken = any(
            tx.get("predecessor_index") == end_index 
            for tx in mempool
        )
        if not taken:
            return end
            
    return None

def find_bifurcation_point(blockchain: List[Dict], mempool: List[Dict]) -> Tuple[Dict, int]:
    """Find the best block to bifurcate from"""
    # Start with the most recent block
    if not blockchain:
        return None, 0
        
    current_block = blockchain[-1]
    current_index = len(blockchain) - 1
    current_layer = current_block.get("layer", 0)
    
    # Walk back until we find a block we can bifurcate from
    while current_index >= 0:
        # Count pending transactions already bifurcating from this block
        pending_bifurcations = sum(
            1 for tx in mempool
            if tx.get("predecessor_index") == current_index
        )
        
        # If this block doesn't have too many pending bifurcations, use it
        if pending_bifurcations < 2:  # Allow up to 2 branches
            return blockchain[current_index], current_layer + 1
            
        current_index -= 1
        current_block = blockchain[current_index]
        current_layer = current_block.get("layer", 0)
        
    return None, 0

def create_transaction_block(
    sender: str,
    receiver: str,
    amount: float,
    signature: str,
    timestamp: float,
    blockchain: List[Dict],
    mempool: List[Dict]
) -> Dict:
    """Create a new transaction block with predecessor and layer information"""
    # Find available chain end
    available_end = find_available_end(blockchain, mempool)
    
    if available_end:
        # Use available end
        predecessor_index = blockchain.index(available_end)
        layer = available_end.get("layer", 0)
    else:
        # Need to bifurcate
        bifurcation_block, new_layer = find_bifurcation_point(blockchain, mempool)
        if bifurcation_block:
            predecessor_index = blockchain.index(bifurcation_block)
            layer = new_layer
        else:
            # Empty blockchain, start at beginning
            predecessor_index = None
            layer = 0
    
    # Calculate balances
    sender_balance_before = get_balance(sender, blockchain)
    receiver_balance_before = get_balance(receiver, blockchain)
    
    block = {
        "sender": sender,
        "receiver": receiver,
        "amount": amount,
        "timestamp": timestamp,
        "signature": signature,
        "predecessor_index": predecessor_index,
        "layer": layer,
        "sender_balance_before": sender_balance_before,
        "sender_balance_after": sender_balance_before - amount,
        "receiver_balance_before": receiver_balance_before,
        "receiver_balance_after": receiver_balance_before + amount
    }
    
    return block

def verify_signature(transaction: dict) -> bool:
    """Verify that a transaction's signature is valid"""
    try:
        public_key_bytes = base58.b58decode(transaction['sender'])
        verifying_key = ecdsa.VerifyingKey.from_string(public_key_bytes, curve=ecdsa.SECP256k1)
        
        # Recreate the message that was signed
        message = f"{transaction['sender']}{transaction['receiver']}{transaction['amount']}{transaction['timestamp']}"
        
        signature = base58.b58decode(transaction['signature'])
        return verifying_key.verify(signature, message.encode())
    except Exception as e:
        print(f"Verification error: {e}")
        return False

def sign_transaction(private_key_str: str, sender: str, receiver: str, amount: float, timestamp: float) -> str:
    """Sign transaction data and return the signature"""
    private_key_bytes = base58.b58decode(private_key_str)
    signing_key = ecdsa.SigningKey.from_string(private_key_bytes, curve=ecdsa.SECP256k1)
    
    message = f"{sender}{receiver}{amount}{timestamp}"
    signature = signing_key.sign(message.encode())
    return base58.b58encode(signature).decode()

def generate_keypair() -> tuple:
    """Generate a new ECDSA keypair and return base58 encoded strings"""
    private_key = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1)
    public_key = private_key.get_verifying_key()
    
    private_key_str = base58.b58encode(private_key.to_string()).decode()
    public_key_str = base58.b58encode(public_key.to_string()).decode()
    
    return private_key_str, public_key_str

def mint_burn_test():
    """Test function for mint/burn operations that generates a random number between 0.1 and 1"""
    random_amount = round(random.uniform(0.1, 1.0), 2)
    print(f"\nGenerated random amount for testing: {random_amount} PASTA")
    return random_amount

def main_menu():
    """Main CLI interface for the PaSta cryptocurrency network.
    Provides options to:
    - Generate new keypairs for transactions
    - Create and sign new transactions
    - View pending transactions in the mempool
    - View the current blockchain state
    - Test mint/burn functionality
    """
    ensure_network_dirs()
    
    while True:
        print("\nPaSta Transaction CLI:")
        print("1. Generate new keypair")
        print("2. Create transaction")
        print("3. View mempool")
        print("4. View blockchain")
        print("5. Test Mint/Burn")
        print("6. Exit")
        
        choice = input("\nEnter your choice (1-6): ")
        
        if choice == "1":
            priv, pub = generate_keypair()
            print("\nGenerated new keypair!")
            print(f"Private key: {priv}")
            print(f"Public key (address): {pub}")
            print("\nSAVE THESE KEYS! They won't be stored locally.")
            
        elif choice == "2":
            blockchain = load_json("blockchain.json", [])
            mempool = load_json("mempool.json", [])
            
            # Get transaction details
            private_key = input("Enter your private key: ")
            sender = input("Enter your public key (sender address): ")
            receiver = input("Enter receiver's public key: ")
            amount = float(input("Enter amount: "))
            
            try:
                # Create transaction timestamp
                timestamp = time.time()
                
                # Sign the transaction
                signature = sign_transaction(private_key, sender, receiver, amount, timestamp)
                
                # Create the full transaction block with same timestamp
                transaction = create_transaction_block(
                    sender, receiver, amount, signature, timestamp,
                    blockchain, mempool
                )
                
                # Verify the signature
                if verify_signature(transaction):
                    print("\nSignature verified successfully!")
                    mempool.append(transaction)
                    save_json("mempool.json", mempool)
                    
                    print("Transaction created and added to mempool successfully!")
                    print("Transaction details:")
                    print(json.dumps(transaction, indent=2))
                else:
                    print("\nError: Signature verification failed!")
                    
            except Exception as e:
                print(f"\nError creating transaction: {str(e)}")
            
        elif choice == "3":
            mempool = load_json("mempool.json", [])
            if not mempool:
                print("\nMempool is empty")
            else:
                print("\nCurrent mempool:")
                print(json.dumps(mempool, indent=2))
                
        elif choice == "4":
            blockchain = load_json("blockchain.json", [])
            if not blockchain:
                print("\nBlockchain is empty")
            else:
                print("\nCurrent blockchain:")
                print(json.dumps(blockchain, indent=2))
                
        elif choice == "5":
            print("\nTesting Mint/Burn functionality...")
            amount = mint_burn_test()
            print(f"This amount ({amount} PASTA) would be used for minting/burning in the real implementation")
                
        elif choice == "6":
            print("Goodbye!")
            break
            
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main_menu()
