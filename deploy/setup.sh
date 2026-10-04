#!/usr/bin/env bash
# Set up (or update) a PaSta seed node on a fresh Ubuntu server. Run as root.
# Idempotent: running it again pulls the code, reinstalls and restarts the node.
#
#   bash deploy/setup.sh <domain> [git-ref]
#
# See deploy/README.md for what it does and what it leaves to you.
set -euo pipefail

DOMAIN="${1:?usage: setup.sh <domain> [git-ref]}"
REF="${2:-main}"
REPO="https://github.com/pastacoin/pastacoin.git"
HOME_DIR=/opt/pasta
DATA_DIR=/var/lib/pasta
ENV_FILE=/etc/pasta-node.env

export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get upgrade -y -q
apt-get install -y -q git python3-venv caddy ufw unattended-upgrades

# Firewall: SSH and the web ports only. The node itself listens on localhost.
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# SSH: keys only.
printf 'PasswordAuthentication no\nKbdInteractiveAuthentication no\n' > /etc/ssh/sshd_config.d/01-keys-only.conf
sshd -t
systemctl try-reload-or-restart ssh

# An unprivileged account runs the node.
id pasta >/dev/null 2>&1 || useradd --system --create-home --home-dir "$HOME_DIR" --shell /usr/sbin/nologin pasta
install -d -o pasta -g pasta "$DATA_DIR"

# Code and environment.
if [ ! -d "$HOME_DIR/src/.git" ]; then
    runuser -u pasta -- git clone -q "$REPO" "$HOME_DIR/src"
fi
runuser -u pasta -- git -C "$HOME_DIR/src" fetch -q --prune origin
runuser -u pasta -- git -C "$HOME_DIR/src" checkout -q --detach "origin/$REF"
[ -x "$HOME_DIR/venv/bin/python" ] || runuser -u pasta -- python3 -m venv "$HOME_DIR/venv"
runuser -u pasta -- "$HOME_DIR/venv/bin/pip" install -q --upgrade pip
runuser -u pasta -- "$HOME_DIR/venv/bin/pip" install -q -e "$HOME_DIR/src[server]"

# Settings file: created once, never overwritten.
if [ ! -f "$ENV_FILE" ]; then
    printf '# Address credited with the genesis coins when this node starts a NEW chain.\n# Ignored once %s/chain.json exists.\nPASTA_GENESIS_ADDRESS=\n' "$DATA_DIR" > "$ENV_FILE"
    chmod 644 "$ENV_FILE"
fi

install -m 644 "$HOME_DIR/src/deploy/pasta-node.service" /etc/systemd/system/pasta-node.service
sed "s/__DOMAIN__/$DOMAIN/g" "$HOME_DIR/src/deploy/Caddyfile" > /etc/caddy/Caddyfile
systemctl daemon-reload
systemctl enable -q caddy
systemctl reload caddy || systemctl restart caddy

if [ -f "$DATA_DIR/chain.json" ] || grep -q '^PASTA_GENESIS_ADDRESS=.\+' "$ENV_FILE"; then
    systemctl enable -q pasta-node
    systemctl restart pasta-node
    sleep 2
    systemctl --no-pager --lines=0 status pasta-node | head -4
    echo "Node: $(curl -s --max-time 5 http://127.0.0.1:5000/status | head -c 200)"
else
    echo "No chain yet. Put the genesis address in $ENV_FILE (PASTA_GENESIS_ADDRESS=...) and run this script again."
fi
echo "Code at $(runuser -u pasta -- git -C "$HOME_DIR/src" rev-parse --short HEAD) ($REF). Domain $DOMAIN."
