import json
import os
from typing import Dict, List
from collections import defaultdict

class BlockchainVisualizer:
    def __init__(self):
        self.network_path = "C:\\PastaNetwork"
        self.blockchain = self.load_json("blockchain.json", [])
        
        if not self.blockchain:
            raise ValueError("Blockchain not found. Please run fake-blockchain-gen.py first.")
    
    def load_json(self, filename: str, default):
        """Load JSON file from network path"""
        filepath = os.path.join(self.network_path, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                return json.load(f)
        return default
    
    def generate_mermaid_diagram(self) -> str:
        """Generate a Mermaid diagram representation of the blockchain"""
        # Group blocks by layer
        layers = defaultdict(list)
        for block in self.blockchain:
            layers[block["layer"]].append(block)
        
        # Sort blocks within each layer by index
        for layer in layers:
            layers[layer].sort(key=lambda x: x["index"])
        
        # Generate Mermaid diagram
        diagram = ["graph TD"]
        
        # Add blocks
        for layer in sorted(layers.keys()):
            for block in layers[layer]:
                # Create block label with truncated addresses and amount
                sender = block["sender"][:8] + "..." if block["sender"] != "genesis" else "genesis"
                receiver = block["receiver"][:8] + "..."
                amount = block["amount"]
                mintburn = block["mintburn"]
                
                block_label = f"{block['index']}<br/>"
                block_label += f"From: {sender}<br/>"
                block_label += f"To: {receiver}<br/>"
                block_label += f"Amount: {amount}<br/>"
                block_label += f"Mintburn: {mintburn}"
                
                # Add block node
                diagram.append(f"    {block['index']}[{block_label}]")
        
        # Add connections between blocks
        for block in self.blockchain:
            if block["predecessor_index"] is not None:
                # Add connection from predecessor
                diagram.append(f"    {block['predecessor_index']} --> {block['index']}")
            
            if block["validating_block_id"] is not None:
                # Add validation connection with different style
                diagram.append(f"    {block['validating_block_id']} -.-> {block['index']}")
        
        # Add styling
        diagram.append("\n    %% Styling")
        diagram.append("    classDef block fill:#f9f,stroke:#333,stroke-width:2px")
        diagram.append("    classDef genesis fill:#9ff,stroke:#333,stroke-width:2px")
        diagram.append("    class 0 genesis")
        
        return "\n".join(diagram)
    
    def save_diagram(self, diagram: str) -> None:
        """Save the Mermaid diagram to a file"""
        diagram_path = os.path.join(self.network_path, "blockchain_diagram.md")
        with open(diagram_path, "w") as f:
            f.write("```mermaid\n")
            f.write(diagram)
            f.write("\n```")
        
        print(f"\nBlockchain diagram saved to {diagram_path}")
        print("\nYou can view this diagram by:")
        print("1. Opening the .md file in a Markdown viewer that supports Mermaid")
        print("2. Using an online Mermaid editor (https://mermaid.live)")
        print("3. Using VS Code with a Mermaid extension")
        
        # Also save a text summary
        summary_path = os.path.join(self.network_path, "blockchain_summary.txt")
        with open(summary_path, "w") as f:
            f.write("Blockchain Summary:\n")
            f.write(f"Total blocks: {len(self.blockchain)}\n")
            f.write(f"Number of layers: {max(block['layer'] for block in self.blockchain) + 1}\n\n")
            
            # Group by layer
            layers = defaultdict(list)
            for block in self.blockchain:
                layers[block["layer"]].append(block)
            
            for layer in sorted(layers.keys()):
                f.write(f"\nLayer {layer}:\n")
                for block in sorted(layers[layer], key=lambda x: x["index"]):
                    f.write(f"  Block {block['index']}: ")
                    f.write(f"From {block['sender'][:8]}... to {block['receiver'][:8]}... ")
                    f.write(f"Amount: {block['amount']}, Mintburn: {block['mintburn']}\n")
        
        print(f"\nBlockchain summary saved to {summary_path}")

if __name__ == "__main__":
    visualizer = BlockchainVisualizer()
    diagram = visualizer.generate_mermaid_diagram()
    visualizer.save_diagram(diagram) 