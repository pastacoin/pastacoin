# PaSta Coin: Passively Stable Cryptocurrency

PaSta is a novel blockchain architecture designed to create a practical, scalable cryptocurrency for everyday transactions. PaSta is a Proof-of-Work type cryptocurrency, relies on "longest chain" concensus rules and in many other additional ways relies heavily on learnings from the Bitcoin Blockchain. It addresses three fundamental challenges in current cryptocurrency systems: price stability, transaction throughput, and decentralized validation.

A working draft of the whitepaper describing this project can be found here: https://docs.google.com/document/d/16TWRU0hxGe5E3mB4EnAzSYjfOsMuH8AT/edit?usp=sharing&ouid=113569012516612057458&rtpof=true&sd=true

## Key Features

### Algorithmic Stability Control
Unlike traditional stablecoins that require pegging to external currencies, PaSta implements internal stability mechanisms that:
- Monitor average transaction sizes across the network to detect price trends
- Automatically adjust money supply through small minting or burning operations within transactions

### Dynamic Chain Architecture
PaSta enables parallel processing through a scalable chain structure:
- One transaction per block
- Controlled chain bifurcation allows splits when the network is saturated
- Aggregation blocks merge blocks back towards the main chain
- Block times get shorter the further from the main chain a block gets (layering)
- If a block initiates a split, it must also perform an aggregation to be eligible for validation
- Balance blocks serve as validated checkpoints to optimize transaction history
- Maintains eventual consistency while enabling dramatically higher throughput

### User-Based Validation
Instead of relying on dedicated miners, PaSta distributes validation among network participants:
- Instead of miners competing for a coin reward, users compete to have their transactions accepted
- Prior to a transaction block being eligible for validation the node must first validate other transactions
- Once a block is eligible for validation other users must validate it
- Transaction privileges are tied directly to blockchain storage contribution
- Higher layer transactions (further from teh main chain, smaller block time) process quickly with minimal validation
- Number of validators scales perfectly with number of transactions (because the nodes executing transactions are also the validators)

## Core Components

### PastaMachine (Full Node)
- Chain data management
- Transaction processing
- Validation mechanisms
- Stability control
- State management
- Network communication

### PastaWallet (Light Client)
- Basic transaction creation
- Local validation
- Balance management
- User interface
- Address book

### PastaMonitor
- Network visualization
- Chain state monitoring
- Performance metrics
- Development tools

### PastaTester
- Network simulation
- Stability testing
- Attack modeling
- Performance testing

### FakeChainMaker
- Create fake theoretical blockchains
- Integrate with PastaTester for simulation 

## Technical Benefits

- Truly decentralized: Validation distributed among users, no miners
- Scalable: Validator availability naturally scales with transaction volume
- Stable: Built-in mechanisms to maintain price stability
- Efficient: Balance blocks optimize transaction history storage
- Fast: Parallel processing enables high transaction throughput

## Design Philosophy

PaSta is designed specifically as a medium of exchange rather than a store of value or investment vehicle. Its value is programmed to remain the same over time:
- Discourages speculative investment and hoarding
- Promotes active use in transactions
- Minimizes short-term value fluctuations
- May help distinguish it from commodities or investment assets (from a regulatory perspective)

## Development Status

This project is currently in the conceptual phase. Next steps include:
- Developing detailed technical specifications
- Creating proof-of-concept implementations
- Establishing testing frameworks
- Conducting security analysis
- Building community support

## Testing the System

### Prerequisites
- Python 3.7 or higher
- Required Python packages: `flask`, `requests`, `ecdsa`, `base58`

Install dependencies:
```bash
pip install flask requests ecdsa base58
```

### Running the Test Environment

1. Start the Node:
```bash
python node.py -p 5000
```

2. In a new terminal, start the CLI:
```bash
python pasta-cli.py --node http://localhost:5000
```

### Testing Transaction Flow

1. Generate Addresses:
   - In the CLI, choose option 1 to generate a new keypair
   - Save both the private and public keys
   - Generate at least 2 keypairs (for sender and receiver)

2. Create Initial Transaction:
   - Choose option 2 to create a transaction
   - Enter the sender's private key
   - Enter the sender's public key
   - Enter the receiver's public key
   - Enter an amount (e.g., 10.0)
   - This creates a transaction in State A

3. View Transaction State:
   - Choose option 3 to view the mempool
   - Verify the transaction is in State A

4. Advance to State B:
   - Choose option 7
   - Select the transaction to validate
   - Create a new transaction that will validate the selected one
   - This advances the first transaction to State B

5. Advance to State C:
   - Choose option 8
   - Select the transaction to be validated
   - Create a new transaction that will validate it
   - This advances the transaction to State C

6. Verify Final State:
   - Use option 4 to view the blockchain
   - Use option 5 to check balances

### Testing Notes
- Each transaction must go through states A -> B -> C
- State B requires validating another transaction
- State C requires being validated by another transaction
- The genesis block starts in State C
- Hash synchronization occurs between states B and C

## Contributing

While we're still in early stages, we welcome discussion and contributions from developers interested in:
- Blockchain architecture
- Cryptocurrency stability mechanisms
- Distributed systems
- Network security
- Economic modeling
- User interface design


---
*Note: This project is under active development. Features and specifications are subject to change as we refine the system architecture and implementation details.*
