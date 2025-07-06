# Shim file for backward compatibility
from pasta.network.server import app, run

if __name__ == "__main__":
    run() 