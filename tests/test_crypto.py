from pasta.core.crypto import (
    canonical_payload,
    compute_tx_id,
    generate_keypair,
    public_key_for,
    sign_transaction,
    verify_transaction,
)


def test_canonical_payload_is_stable():
    a = canonical_payload("S", "R", 1, 5)
    b = canonical_payload("S", "R", 1.0, 5)
    assert a == b == '{"amount":1,"receiver":"R","sender":"S","timestamp":5}'
    assert compute_tx_id("S", "R", 1, 5) == compute_tx_id("S", "R", 1.0, 5)
    assert compute_tx_id("S", "R", 1, 5) != compute_tx_id("S", "R", 1, 6)


def test_sign_verify_roundtrip():
    kp = generate_keypair()
    sig = sign_transaction(kp["private_key"], kp["public_key"], "RCV", 250, 100)
    assert verify_transaction(kp["public_key"], "RCV", 250, 100, sig)


def test_tampered_fields_fail():
    kp = generate_keypair()
    sig = sign_transaction(kp["private_key"], kp["public_key"], "RCV", 250, 100)
    assert not verify_transaction(kp["public_key"], "RCV", 260, 100, sig)
    assert not verify_transaction(kp["public_key"], "RCV", 250.5, 100, sig)   # not whole base units
    assert not verify_transaction(kp["public_key"], "OTHER", 250, 100, sig)
    assert not verify_transaction(kp["public_key"], "RCV", 250, 101, sig)


def test_wrong_key_and_garbage_fail():
    kp, other = generate_keypair(), generate_keypair()
    sig = sign_transaction(kp["private_key"], kp["public_key"], "RCV", 1, 1)
    assert not verify_transaction(other["public_key"], "RCV", 1, 1, sig)
    assert not verify_transaction(kp["public_key"], "RCV", 1, 1, None)
    assert not verify_transaction(kp["public_key"], "RCV", 1, 1, "not-base58-!!")
    assert not verify_transaction("not a key", "RCV", 1, 1, sig)


def test_public_key_for_matches_generated():
    kp = generate_keypair()
    assert public_key_for(kp["private_key"]) == kp["public_key"]
