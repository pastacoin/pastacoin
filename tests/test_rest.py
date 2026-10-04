import pytest

from pasta import Node, sign_transaction


@pytest.fixture
def client(founder):
    node = Node(genesis_receiver=founder.pub)
    app = node.create_flask_app("test_app")
    app.config["TESTING"] = True
    return app.test_client(), node


def _post(client, url, body):
    return client.post(url, json=body)


def test_end_to_end_over_rest(client, wallet):
    c, node = client
    kp = c.get("/generate_keypair").get_json()
    assert set(kp) == {"private_key", "public_key"}
    bob = wallet()

    bootstrap = c.get("/mempool").get_json()[0]["tx_id"]
    ts = wallet.next_timestamp()
    sig = sign_transaction(kp["private_key"], kp["public_key"], bob.pub, 0, ts)
    r = _post(c, "/create_transaction", {"sender": kp["public_key"], "receiver": bob.pub,
                                         "amount": 0, "timestamp": ts, "signature": sig})
    assert r.status_code == 201
    tx = r.get_json()["tx"]
    assert tx["state"] == "A" and tx["mint_amount"] == 0

    r = _post(c, "/validate", {"my_tx_id": tx["tx_id"], "target_tx_id": bootstrap})
    assert r.status_code == 200
    body = r.get_json()
    assert body["my_tx"]["state"] == "B" and body["finalized"]["state"] == "C"

    assert c.get("/blockchain").get_json()[1]["validator_address"] == kp["public_key"]
    assert c.get(f"/mempool/{tx['tx_id']}").get_json()["state"] == "B"
    assert c.get(f"/balance/{bob.pub}").get_json()["balance"] == 0
    assert c.get(f"/balance/{node.genesis_receiver}").get_json()["balance"] == 1_000_000_000   # 10 PASTA
    assert c.get("/verify").get_json() == {"ok": True, "problems": []}
    status = c.get("/status").get_json()
    assert status["height"] == 2 and status["mempool_size"] == 1
    assert status["units_per_pasta"] == 100_000_000
    assert status["stability"]["supply"] == 1_000_000_000


def test_rest_error_mapping(client, wallet):
    c, _ = client
    alice, bob = wallet(), wallet()
    r = _post(c, "/create_transaction", {"sender": alice.pub, "receiver": bob.pub, "amount": 0})
    assert r.status_code == 400 and r.get_json()["type"] == "InvalidSignature"
    r = _post(c, "/create_transaction", {"sender": alice.pub})
    assert r.status_code == 400 and "missing" in r.get_json()["error"]
    r = _post(c, "/validate", {"my_tx_id": "x", "target_tx_id": "y"})
    assert r.status_code == 400 and r.get_json()["type"] == "NotFound"
    assert c.get("/mempool/nope").status_code == 400
    r = _post(c, "/create_transaction", {"sender": "GENESIS", "receiver": bob.pub, "amount": 5})
    assert r.status_code == 400 and r.get_json()["type"] == "InvalidTransaction"
    r = _post(c, "/create_transaction", {"sender": alice.pub, "receiver": bob.pub, "amount": 0.5})
    assert r.status_code == 400 and "whole number" in r.get_json()["error"]
    assert _post(c, "/advance_b", {}).status_code == 410
    assert _post(c, "/advance_c", {}).status_code == 410
