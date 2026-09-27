import time

import pytest

from pasta import Node, generate_keypair, sign_transaction


class Wallet:
    """Test helper: a keypair that can submit signed transactions to a node."""

    _clock = [int(time.time())]

    def __init__(self):
        kp = generate_keypair()
        self.priv = kp["private_key"]
        self.pub = kp["public_key"]

    @classmethod
    def next_timestamp(cls) -> int:
        # strictly increasing so identical (sender, receiver, amount) never collide on tx_id
        cls._clock[0] += 1
        return cls._clock[0]

    def send(self, node: Node, receiver: str, amount: float, *, timestamp=None, signature=None):
        ts = timestamp if timestamp is not None else self.next_timestamp()
        sig = signature if signature is not None else sign_transaction(self.priv, self.pub, receiver, amount, ts)
        return node.create_transaction(self.pub, receiver, amount, timestamp=ts, signature=sig)


@pytest.fixture
def wallet():
    return Wallet


@pytest.fixture
def node():
    return Node()


@pytest.fixture
def bootstrap_id(node):
    """tx_id of the State-B bootstrap transaction a fresh node starts with."""
    return node.get_mempool()[0]["tx_id"]


@pytest.fixture
def funded(node, bootstrap_id):
    """Two wallets; ``rich`` holds 10 PASTA on-chain via the bootstrap mint.

    Flow: minter sends a zero-value tx to rich (mints 10), validates bootstrap (minter tx -> B).
    A helper wallet then sends a zero-value tx and validates minter's tx, which finalizes
    the mint so ``rich`` has 10 PASTA on chain.
    """
    minter, rich, helper = Wallet(), Wallet(), Wallet()
    mint_tx = minter.send(node, rich.pub, 0)
    node.validate(mint_tx["tx_id"], bootstrap_id)
    helper_tx = helper.send(node, helper.pub, 0)
    node.validate(helper_tx["tx_id"], mint_tx["tx_id"])
    assert node.balance_for(rich.pub) == 10.0
    return {"node": node, "rich": rich, "helper": helper, "helper_tx": helper_tx, "minter": minter}
