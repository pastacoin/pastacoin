**The Pasta Machine** is the desktop wallet and node for the PaSta prototype chain.

Download `PastaMachine.exe` and run it. There is nothing to install.

- It follows the public test network (`seed.pastacoin.org`), keeps its own copy of the chain
  on your computer and checks every block itself.
- It creates a wallet on first run. Wallets are kept in a file on your computer that is
  **not encrypted**; use Wallet > Back up to save a copy.
- Network > Private chain on this computer starts a chain of your own instead.

Things to know:

- **Windows will warn you.** The program is not code-signed, so SmartScreen shows "Windows
  protected your PC". Choose "More info", then "Run anyway". The file was built by GitHub
  Actions from the tagged source in this repository; `PastaMachine.exe.sha256` is its checksum.
- **This is a test chain.** Its coins have no value and it can be reset at any time. Don't buy
  pastacoin.

To run from source instead: `pip install -e ".[gui]"` then `python -m pasta.frontends.desktop`.
