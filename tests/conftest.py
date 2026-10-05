import time

import pytest

from pasta import Node, generate_keypair, sign_transaction
from pasta.core.units import UNITS_PER_PASTA

P = UNITS_PER_PASTA   # one PASTA in base units; tests write amounts as 4 * P


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

    def send(self, node: Node, receiver: str, amount: int, *, timestamp=None, signature=None):
        ts = timestamp if timestamp is not None else self.next_timestamp()
        sig = signature if signature is not None else sign_transaction(self.priv, self.pub, receiver, amount, ts)
        return node.create_transaction(self.pub, receiver, amount, timestamp=ts, signature=sig)


def pay(node: Node, sender: Wallet, receiver: str, amount: int) -> dict:
    """Send a payment and see it finalized. Returns the on-chain block.

    The payment validates whatever State-B transaction is waiting (the bootstrap, or the
    last helper's), then a fresh helper wallet posts a zero-amount transaction and
    validates the payment. Each call therefore adds two blocks: a zero-amount one and
    the payment.
    """
    tx = sender.send(node, receiver, amount)
    target = next(t for t in node.get_mempool() if t["state"] == "B" and t["sender_address"] != sender.pub)
    node.validate(tx["tx_id"], target["tx_id"])
    helper = Wallet()
    helper_tx = helper.send(node, helper.pub, 0)
    return node.validate(helper_tx["tx_id"], tx["tx_id"])["finalized"]


@pytest.fixture
def wallet():
    return Wallet


@pytest.fixture
def founder():
    """The wallet the genesis block credits with the genesis supply (10 PASTA)."""
    return Wallet()


@pytest.fixture
def node(founder):
    return Node(genesis_receiver=founder.pub)


@pytest.fixture
def bootstrap_id(node):
    """tx_id of the State-B bootstrap transaction a fresh node starts with."""
    return node.get_mempool()[0]["tx_id"]


@pytest.fixture
def funded(node, founder, bootstrap_id):
    """``rich`` is the founder (10 PASTA from genesis); ``helper`` has nothing.

    ``helper_tx`` is a zero-amount transaction of helper's, already in State B (it validated
    the bootstrap), so the next transaction has something to validate. Chain height is 2.
    """
    helper = Wallet()
    helper_tx = helper.send(node, helper.pub, 0)
    node.validate(helper_tx["tx_id"], bootstrap_id)
    assert node.balance_for(founder.pub) == 10 * P
    return {"node": node, "rich": founder, "helper": helper, "helper_tx": helper_tx}
