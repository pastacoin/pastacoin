# Running a seed node

A seed is an ordinary PaSta node on a public address. Nothing about it is special: it runs
the code in this repository, and anyone can stand up another one with the three files here.
The project's own seed is `seed.pastacoin.org`.

Until nodes gossip with each other (Phase 3, issues #16 and #17) a seed is also the only
machine that orders transactions for its chain. Other nodes copy its chain and check every
block themselves.

## What you need

- A small Linux server (Ubuntu 24.04 or later; 1 vCPU and 1 GB is enough) that you can reach
  as root over SSH with a key.
- A DNS name pointing at it (an A record), for the HTTPS certificate.
- An address to receive the genesis coins if you are starting a new chain. Generate the
  wallet on your own machine and keep the private key there; the server never needs it.

## Set up

    git clone https://github.com/pastacoin/pastacoin.git /root/pastacoin
    bash /root/pastacoin/deploy/setup.sh seed.example.org

The first run stops before starting the node and asks for the genesis address:

    nano /etc/pasta-node.env        # PASTA_GENESIS_ADDRESS=<your address>
    bash /root/pastacoin/deploy/setup.sh seed.example.org

`setup.sh` is safe to run again; that is also how you update to newer code. A second
argument selects a branch or tag (default `main`).

## What the script does

- Installs updates, git, Python, Caddy and a firewall; opens ports 22, 80 and 443 only.
- Turns off password logins over SSH.
- Creates an unprivileged `pasta` account; code in `/opt/pasta/src`, chain in
  `/var/lib/pasta/chain.json`.
- Runs the node under systemd (`pasta-node.service`) with one gunicorn worker bound to
  localhost, and Caddy in front of it for HTTPS.

## Operating it

    systemctl status pasta-node          # is it running
    journalctl -u pasta-node -n 50       # recent log
    curl -s https://<domain>/status      # height, supply, mint rule state
    curl -s https://<domain>/verify      # full chain check
    cp /var/lib/pasta/chain.json ~/      # backup: the whole chain is this one file

To start a chain over, stop the service, delete `/var/lib/pasta/chain.json`, and start it.

## Limits of the prototype

- No rate limiting: anyone can post transactions. Zero-amount transactions are free.
- The chain file is rewritten after every change, which is fine for thousands of blocks and
  not for millions.
- `GET /generate_keypair` makes a key on the server and is there for convenience only. Real
  wallets generate keys locally.
