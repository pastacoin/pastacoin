"""Keys, signatures and the canonical transaction payload.

Every client (CLI, desktop wizard, web prototype) and the node must agree on the
exact bytes that get signed. That agreement lives here and nowhere else:

* :func:`canonical_payload` renders ``(sender, receiver, amount, timestamp)`` as
  compact JSON with sorted keys.
* :func:`compute_tx_id` is the SHA-256 of that payload and is the stable identity of a
  transaction for its whole life-cycle (mempool and chain).
* :func:`sign_transaction` / :func:`verify_transaction` sign and check that payload
  with secp256k1 ECDSA over SHA-256. Keys and signatures travel as Base58 text.

The sender address *is* the Base58 public key (prototype simplification).
"""
from __future__ import annotations

import hashlib
import json

import base58
import ecdsa

GENESIS_ADDRESS = "GENESIS"


# ------------------------------------------------------------------ keys ----

def generate_keypair() -> dict:
    """Generate a secp256k1 keypair; return ``{"private_key", "public_key"}`` in Base58."""
    priv = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1)
    pub = priv.get_verifying_key()
    return {
        "private_key": base58.b58encode(priv.to_string()).decode(),
        "public_key": base58.b58encode(pub.to_string()).decode(),
    }


def public_key_for(private_key_b58: str) -> str:
    """Derive the Base58 public key (address) from a Base58 private key."""
    sk = ecdsa.SigningKey.from_string(base58.b58decode(private_key_b58), curve=ecdsa.SECP256k1)
    return base58.b58encode(sk.get_verifying_key().to_string()).decode()


# ----------------------------------------------------------- payload ----

def canonical_payload(sender: str, receiver: str, amount: float, timestamp: int) -> str:
    """The exact string that is hashed for ``tx_id`` and signed by the sender."""
    return json.dumps(
        {
            "sender": sender,
            "receiver": receiver,
            "amount": float(amount),
            "timestamp": int(timestamp),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def compute_tx_id(sender: str, receiver: str, amount: float, timestamp: int) -> str:
    """Stable transaction identity: SHA-256 hex of the canonical payload."""
    return hashlib.sha256(canonical_payload(sender, receiver, amount, timestamp).encode()).hexdigest()


# --------------------------------------------------------- signatures ----

def sign_message(private_key_b58: str, message: str) -> str:
    """Sign an arbitrary string; returns a Base58 signature (secp256k1, SHA-256)."""
    sk = ecdsa.SigningKey.from_string(base58.b58decode(private_key_b58), curve=ecdsa.SECP256k1)
    sig = sk.sign(message.encode(), hashfunc=hashlib.sha256)
    return base58.b58encode(sig).decode()


def verify_message(public_key_b58: str, message: str, signature_b58: str) -> bool:
    """Return True iff ``signature_b58`` is a valid signature of ``message`` by ``public_key_b58``.

    Never raises: malformed keys or signatures simply return False.
    """
    try:
        vk = ecdsa.VerifyingKey.from_string(base58.b58decode(public_key_b58), curve=ecdsa.SECP256k1)
        return vk.verify(base58.b58decode(signature_b58), message.encode(), hashfunc=hashlib.sha256)
    except Exception:  # noqa: BLE001 - any decode/verify failure means "not valid"
        return False


def sign_transaction(private_key_b58: str, sender: str, receiver: str, amount: float, timestamp: int) -> str:
    """Sign the canonical payload of a transaction."""
    return sign_message(private_key_b58, canonical_payload(sender, receiver, amount, timestamp))


def verify_transaction(sender: str, receiver: str, amount: float, timestamp: int, signature_b58: str | None) -> bool:
    """Check a transaction signature against the sender address (its public key)."""
    if not signature_b58:
        return False
    return verify_message(sender, canonical_payload(sender, receiver, amount, timestamp), signature_b58)
