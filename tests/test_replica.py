"""A replica follows a seed, verifies what it is served, and sends transactions through it."""
import copy

import pytest

from conftest import P, Wallet as KeyPair, pay
from pasta import InsufficientBalance, Node
from pasta.node.replica import Replica, SeedClient, SeedUnreachable
from pasta.wallet import Wallet, WalletStore, confirm, eligible_targets, send_payment


class FlaskSession:
    """Stands in for requests.Session: routes the replica's calls to a Flask test client."""

    def __init__(self, node):
        self.node = node
        self.client = node.create_flask_app("seed_under_test").test_client()
        self.down = False
        self.tamper = None          # optional function(list of blocks) -> list of blocks

    def _wrap(self, r, path=""):
        body = r.get_json()
        if self.tamper and path == "/blockchain":
            body = self.tamper(body)

        class Response:
            status_code = r.status_code

            @staticmethod
            def json():
                return body
        return Response()

    def get(self, url, params=None, timeout=None):
        if self.down:
            import requests
            raise requests.ConnectionError("down")
        path = url.split("http://seed", 1)[1]
        return self._wrap(self.client.get(path, query_string=params or {}), path)

    def post(self, url, json=None, timeout=None):
        if self.down:
            import requests
            raise requests.ConnectionError("down")
        return self._wrap(self.client.post(url.split("http://seed", 1)[1], json=json))


@pytest.fixture
def seed(founder):
    return Node(genesis_receiver=founder.pub)


@pytest.fixture
def session(seed):
    return FlaskSession(seed)


def make_replica(session, path=None):
    return Replica("http://seed", str(path) if path else None, client=SeedClient("http://seed", session=session))


def as_wallet(w: KeyPair, name="w") -> Wallet:
    return Wallet(name, w.priv, w.pub)


def test_replica_copies_and_verifies_the_seed_chain(seed, session, founder, wallet):
    bob = wallet()
    for _ in range(3):
        pay(seed, founder, bob.pub, P)
    r = make_replica(session)
    assert r.sync() == len(seed.get_blockchain())
    assert r.get_blockchain() == seed.get_blockchain()
    assert r.balance_for(bob.pub) == seed.balance_for(bob.pub) == 3 * P
    assert r.status()["stability"] == seed.status()["stability"]
    assert r.status()["seed"]["online"] is True and r.verify() == []

    pay(seed, founder, bob.pub, P)                 # two more blocks appear on the seed
    assert r.sync() == 2
    assert r.sync() == 0
    assert r.balance_for(bob.pub) == 4 * P


def test_replica_rejects_a_forged_block_and_keeps_what_it_verified(seed, session, founder, wallet):
    bob = wallet()
    pay(seed, founder, bob.pub, P)
    r = make_replica(session)
    r.sync()
    good_height = r.status()["height"]

    pay(seed, founder, bob.pub, P)

    def forge(blocks):
        blocks = copy.deepcopy(blocks)
        blocks[-1]["mint_amount"] = 5 * P          # the seed claims a mint the rule does not allow
        blocks[-1]["receiver_balance_after"] += 5 * P
        return blocks
    session.tamper = forge
    r.sync()
    assert r.status()["height"] == good_height + 1          # the honest block before it was accepted
    assert any("mint_amount" in p or "proof-of-work" in p for p in r.status()["seed"]["rejected"])
    assert r.balance_for(bob.pub) == P                      # the forged credit never counted

    session.tamper = None
    r.sync()
    assert r.status()["seed"]["rejected"] == [] and r.balance_for(bob.pub) == 2 * P


def test_replica_notices_when_the_seed_is_reset(session, seed, founder, wallet, tmp_path):
    pay(seed, founder, wallet().pub, P)
    r = make_replica(session, tmp_path / "copy.json")
    r.sync()
    kept = r.get_blockchain()

    other = Node(genesis_receiver=wallet().pub)             # a different chain behind the same address
    session.client = other.create_flask_app("reset_seed").test_client()
    assert r.sync() == 0
    assert "no longer contains" in r.status()["seed"]["diverged"]
    assert r.get_blockchain() == kept                       # the verified copy is not thrown away silently

    r.reset()
    r.sync()
    assert r.status()["seed"]["diverged"] is None
    assert r.get_blockchain() == other.get_blockchain()


def test_replica_survives_an_unreachable_seed_and_restarts_from_disk(session, seed, founder, wallet, tmp_path):
    bob = wallet()
    pay(seed, founder, bob.pub, P)
    path = tmp_path / "copy.json"
    r = make_replica(session, path)
    r.sync()
    session.down = True
    assert r.sync() == 0
    assert r.status()["seed"]["online"] is False and "cannot reach" in r.status()["seed"]["error"]
    assert r.balance_for(bob.pub) == P                      # still answers from the verified copy

    again = make_replica(session, path)                     # restart while the seed is down
    assert again.get_blockchain() == seed.get_blockchain()
    assert again.balance_for(bob.pub) == P
    with pytest.raises(SeedUnreachable):
        again.create_transaction(bob.pub, founder.pub, 1, timestamp=1, signature="x")


def test_send_and_confirm_through_a_replica(seed, session, founder, wallet):
    r = make_replica(session)
    r.sync()
    alice, bob = as_wallet(founder, "alice"), as_wallet(wallet(), "bob")

    sent = send_payment(r, alice, bob.address, 3 * P)
    assert sent["tx"]["state"] == "B"                       # it validated the bootstrap on the way
    assert sent["validated"]["sender_address"] == "GENESIS"
    assert r.balance_for(bob.address) == 0                  # not final yet

    waiting = eligible_targets(r, bob.address)
    assert [t["tx_id"] for t in waiting] == [sent["tx"]["tx_id"]]
    done = confirm(r, bob, sent["tx"]["tx_id"])
    assert done["finalized"]["state"] == "C" and done["finalized"]["validator_address"] == bob.address
    assert r.balance_for(bob.address) == 3 * P == seed.balance_for(bob.address)
    assert r.balance_for(alice.address) == 7 * P
    assert seed.verify() == [] and r.verify() == []

    with pytest.raises(InsufficientBalance):                # the seed's rejection arrives as the same error
        send_payment(r, bob, alice.address, 50 * P)


def test_flows_work_on_a_local_node_and_identical_sends_do_not_collide(seed, founder, wallet):
    alice, bob = as_wallet(founder), as_wallet(wallet())
    first = send_payment(seed, alice, bob.address, P)
    second = send_payment(seed, alice, bob.address, P)      # same sender, receiver, amount, same second
    assert first["tx"]["tx_id"] != second["tx"]["tx_id"]
    assert second["validated"] is None                      # nothing else was waiting: stays at step 1
    assert second["tx"]["state"] == "A"
    confirm(seed, bob, first["tx"]["tx_id"])
    assert seed.balance_for(bob.address) == P
    with pytest.raises(Exception, match="your own"):
        confirm(seed, alice, second["tx"]["tx_id"])


def test_wallet_store_roundtrip(tmp_path):
    path = tmp_path / "wallets.json"
    store = WalletStore(str(path))
    a = store.create("Main")
    b = store.create("Main")
    assert (a.name, b.name) == ("Main", "Main 2")
    backup = tmp_path / "backup.json"
    store.export_file(a, str(backup))

    other = WalletStore(str(tmp_path / "other.json"))
    imported = other.import_file(str(backup))
    assert imported.address == a.address and imported.name == "Main"
    assert other.import_key(a.private_key) is imported      # importing twice does not duplicate
    with pytest.raises(ValueError):
        other.import_key("not a key")

    reopened = WalletStore(str(path))
    assert [w.address for w in reopened.wallets] == [a.address, b.address]
    reopened.remove(reopened.wallets[0])
    assert [w.address for w in WalletStore(str(path)).wallets] == [b.address]
