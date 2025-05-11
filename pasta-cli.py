import json
# import os # No longer needed for direct file access
import time
import hashlib
import ecdsa
import base58
import random
import requests # Added
import argparse # Added
from typing import Optional, List, Dict, Tuple

# NETWORK_PATH = "C:\\PastaNetwork" # No longer needed

# def ensure_network_dirs(): # Removed
#     """Ensure network directories exist"""
#     if not os.path.exists(NETWORK_PATH):
#         os.makedirs(NETWORK_PATH)

# def load_json(filename: str, default): # Removed
#     filepath = os.path.join(NETWORK_PATH, filename)
#     if os.path.exists(filepath):
#         with open(filepath, 'r') as f:
#             return json.load(f)
#     return default

# def save_json(filename: str, data): # Removed
#     filepath = os.path.join(NETWORK_PATH, filename)
#     with open(filepath, 'w') as f:
#         json.dump(data, f, indent=2)

def get_node_blockchain(node_address: str) -> List[Dict]:
    """Fetches the current blockchain from the node."""
    try:
        response = requests.get(f"{node_address}/blockchain")
        response.raise_for_status() # Raise exception for bad status codes
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching blockchain from {node_address}: {e}")
        return []

def get_node_mempool(node_address: str) -> List[Dict]:
    """Fetches the current mempool from the node."""
    try:
        response = requests.get(f"{node_address}/mempool")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching mempool from {node_address}: {e}")
        return []

def post_transaction_to_node(node_address: str, transaction: Dict) -> bool:
    """Posts a new transaction to the node's mempool."""
    try:
        response = requests.post(f"{node_address}/add_transaction", json=transaction)
        response.raise_for_status()
        print(f"Node response ({response.status_code}): {response.json().get('message')}")
        return response.status_code == 201 # Check if created
    except requests.exceptions.RequestException as e:
        print(f"Error posting transaction to {node_address}: {e}")
        if e.response is not None:
            try:
                print(f"Node error ({e.response.status_code}): {e.response.json().get('message')}")
            except json.JSONDecodeError:
                print(f"Node error ({e.response.status_code}): {e.response.text}")
        return False

def get_balance(address: str, blockchain: List[Dict]) -> float:
    """Calculate balance for an address from blockchain"""
    balance = 0
    for block in blockchain:
        # Assuming genesis block doesn't affect balances in this calculation
        if block["receiver"] == address:
            balance += block["amount"]
        if block["sender"] == address and block["sender"] != "genesis":
            balance -= block["amount"]
    return balance

# Removed functions that relied on direct file access and complex block creation:
# find_chain_ends, find_available_end, find_bifurcation_point, create_transaction_block

# --- Simplified Transaction Creation ---
# The node will handle adding predecessor, layer, etc., when it mines/validates blocks.
# The CLI just creates the core transaction data.

def create_core_transaction(
    sender: str,
    receiver: str,
    amount: float,
    private_key_str: str
) -> Optional[Dict]:
    """Creates the core transaction data and signs it."""
    try:
        timestamp = time.time()
        signature = sign_transaction(private_key_str, sender, receiver, amount, timestamp)

        transaction = {
            # Core transaction data
            "sender": sender,
            "receiver": receiver,
            "amount": amount,
            "timestamp": timestamp,
            "signature": signature,
            
            # State tracking
            "state": "A",  # Initial state
            
            # Hash fields for different states
            "hash_a": None,  # Will be calculated by node
            "hash_b": None,  # Will be set when validating another block
            "hash_c": None,  # Will be set when this block is validated
            
            # Validation metadata
            "validated_block": None,  # ID of the block this transaction will validate
            "validated_by": None,     # ID of the block that validates this transaction
            
            # Predecessor information
            "predecessor_index": None,  # Will be set by node to latest block
            "predecessor_hash": None,   # Will be set by node
        }

        # Verify the signature locally before sending
        if verify_signature(transaction):
            print("\nLocal signature verified successfully before sending.")
            return transaction
        else:
            print("\nError: Local signature verification failed! Transaction not sent.")
            return None
    except Exception as e:
        print(f"\nError creating core transaction: {e}")
        return None

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

def main_menu(node_address: str):
    """Main CLI interface, interacting with a specific PastaNode."""
    while True:
        print(f"\n--- Interacting with Node: {node_address} ---")
        print("PaSta Transaction CLI:")
        print("1. Generate new keypair")
        print("2. Create and Send transaction (State A)")
        print("3. View Node Mempool")
        print("4. View Node Blockchain")
        print("5. Check Balance (from Node Blockchain)")
        print("6. Test Mint/Burn (Local Concept)")
        print("7. Advance Transaction to State B (Validate Another Block)")
        print("8. Advance Transaction to State C (Get Validated)")
        print("9. Exit")

        choice = input("\nEnter your choice (1-9): ")

        if choice == "1":
            priv, pub = generate_keypair()
            print("\nGenerated new keypair!")
            print(f"Private key: {priv}")
            print(f"Public key (address): {pub}")
            print("\nSAVE THESE KEYS! The node does not store private keys.")

        elif choice == "2":
            # Get transaction details
            private_key = input("Enter your private key: ")
            sender = input("Enter your public key (sender address): ")
            receiver = input("Enter receiver's public key: ")
            try:
                amount = float(input("Enter amount: "))
                if amount <= 0:
                    print("Amount must be positive.")
                    continue
            except ValueError:
                print("Invalid amount.")
                continue

            # Create the core transaction data
            core_transaction = create_core_transaction(sender, receiver, amount, private_key)

            if core_transaction:
                print("\nCore transaction created:")
                print(json.dumps(core_transaction, indent=2))
                # Post it to the node
                print(f"\nSending transaction to node {node_address}...")
                post_transaction_to_node(node_address, core_transaction)

        elif choice == "3":
            print(f"\nFetching mempool from {node_address}...")
            mempool = get_node_mempool(node_address)
            if mempool is None:
                print("Failed to fetch mempool.")
            elif not mempool:
                print("Node Mempool is empty")
            else:
                print("\nCurrent Node Mempool:")
                print(json.dumps(mempool, indent=2))

        elif choice == "4":
            print(f"\nFetching blockchain from {node_address}...")
            blockchain = get_node_blockchain(node_address)
            if blockchain is None:
                print("Failed to fetch blockchain.")
            elif not blockchain:
                print("Node Blockchain is empty")
            else:
                print("\nCurrent Node Blockchain:")
                print(json.dumps(blockchain, indent=2))

        elif choice == "5":
            address = input("Enter the public key (address) to check balance for: ")
            print(f"\nFetching blockchain from {node_address} to calculate balance...")
            blockchain = get_node_blockchain(node_address)
            if blockchain is not None:
                balance = get_balance(address, blockchain)
                print(f"\nCalculated balance for {address[:8]}...: {balance} PASTA")
            else:
                print("Could not calculate balance as blockchain fetch failed.")

        elif choice == "6":
            print("\nTesting Mint/Burn functionality...")
            amount = mint_burn_test()
            print(f"This amount ({amount} PASTA) would be used for minting/burning in the real implementation")

        elif choice == "7":
            # Advance transaction to State B
            print("\nAdvancing transaction to State B (Validate Another Block)")
            print("First, let's view the mempool to select a transaction:")
            mempool = get_node_mempool(node_address)
            if not mempool:
                print("No transactions in mempool to validate.")
                continue

            print("\nAvailable transactions in mempool:")
            for i, tx in enumerate(mempool):
                print(f"{i}: {tx.get('signature')[:8]}... (State: {tx.get('state')})")

            try:
                tx_index = int(input("\nEnter the index of the transaction to validate: "))
                if tx_index < 0 or tx_index >= len(mempool):
                    print("Invalid transaction index.")
                    continue

                # Get the transaction to be validated
                tx_to_validate = mempool[tx_index]
                
                # Create a new transaction that will validate the selected one
                private_key = input("Enter your private key: ")
                sender = input("Enter your public key (sender address): ")
                receiver = input("Enter receiver's public key: ")
                try:
                    amount = float(input("Enter amount: "))
                    if amount <= 0:
                        print("Amount must be positive.")
                        continue
                except ValueError:
                    print("Invalid amount.")
                    continue

                # Create the validating transaction
                validating_tx = create_core_transaction(sender, receiver, amount, private_key)
                if validating_tx:
                    # Set it to state B and add validation metadata
                    validating_tx['state'] = 'B'
                    validating_tx['validated_block'] = tx_index
                    
                    print("\nValidating transaction created:")
                    print(json.dumps(validating_tx, indent=2))
                    print(f"\nSending validating transaction to node {node_address}...")
                    post_transaction_to_node(node_address, validating_tx)

            except ValueError:
                print("Invalid input. Please enter a number.")

        elif choice == "8":
            # Advance transaction to State C
            print("\nAdvancing transaction to State C (Get Validated)")
            print("First, let's view the mempool to select a transaction:")
            mempool = get_node_mempool(node_address)
            if not mempool:
                print("No transactions in mempool to validate.")
                continue

            print("\nAvailable transactions in mempool:")
            for i, tx in enumerate(mempool):
                print(f"{i}: {tx.get('signature')[:8]}... (State: {tx.get('state')})")

            try:
                tx_index = int(input("\nEnter the index of the transaction to be validated: "))
                if tx_index < 0 or tx_index >= len(mempool):
                    print("Invalid transaction index.")
                    continue

                # Get the transaction to be validated
                tx_to_validate = mempool[tx_index]
                
                # Create a new transaction that will validate the selected one
                private_key = input("Enter your private key: ")
                sender = input("Enter your public key (sender address): ")
                receiver = input("Enter receiver's public key: ")
                try:
                    amount = float(input("Enter amount: "))
                    if amount <= 0:
                        print("Amount must be positive.")
                        continue
                except ValueError:
                    print("Invalid amount.")
                    continue

                # Create the validating transaction
                validating_tx = create_core_transaction(sender, receiver, amount, private_key)
                if validating_tx:
                    # Set it to state B and add validation metadata
                    validating_tx['state'] = 'B'
                    validating_tx['validated_block'] = tx_index
                    
                    # Update the validated transaction to state C
                    tx_to_validate['state'] = 'C'
                    tx_to_validate['validated_by'] = len(mempool)  # Index of the new validating transaction
                    
                    print("\nValidating transaction created:")
                    print(json.dumps(validating_tx, indent=2))
                    print(f"\nSending validating transaction to node {node_address}...")
                    post_transaction_to_node(node_address, validating_tx)
                    
                    print("\nUpdating validated transaction to state C...")
                    post_transaction_to_node(node_address, tx_to_validate)

            except ValueError:
                print("Invalid input. Please enter a number.")

        elif choice == "9":
            print("Goodbye!")
            break

        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='PastaCoin CLI Client')
    parser.add_argument('--node', type=str, default='http://localhost:5000', help='Address of the PastaNode to connect to.')
    args = parser.parse_args()

    print(f"Attempting to connect to PastaNode at: {args.node}")
    # Quick check if node is reachable (optional)
    try:
        requests.get(f"{args.node}/blockchain", timeout=2) # Check if blockchain endpoint responds
        print(f"Successfully connected to node at {args.node}.")
    except requests.exceptions.RequestException as e:
        print(f"Warning: Could not connect to node at {args.node}. CLI might not function correctly. Error: {e}")
        # Decide if we should exit or let the user try anyway
        # exit(1)

    main_menu(args.node)
