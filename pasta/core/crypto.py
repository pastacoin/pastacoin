"""Basic crypto helpers using ecdsa + base58 (prototype only)."""
import ecdsa, base58

def generate_keypair() -> dict:
    """Generate secp256k1 keypair, return dict with private_key and public_key (base58)."""
    priv = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1)
    pub = priv.get_verifying_key()
    priv_b58 = base58.b58encode(priv.to_string()).decode()
    pub_b58 = base58.b58encode(pub.to_string()).decode()
    return {"private_key": priv_b58, "public_key": pub_b58}


def sign_message(private_key_b58: str, message: str) -> str:
    """Sign arbitrary message string with base58-encoded secp256k1 private key.

    Returns base58-encoded DER signature so it can be easily transported as text.
    """
    priv_bytes = base58.b58decode(private_key_b58)
    sk = ecdsa.SigningKey.from_string(priv_bytes, curve=ecdsa.SECP256k1)
    signature = sk.sign(message.encode())  # default SHA-1 inside ecdsa lib is acceptable for toy
    return base58.b58encode(signature).decode()


def verify_message(public_key_b58: str, message: str, signature_b58: str) -> bool:
    """Verify message signature (matching sign_message)."""
    pub_bytes = base58.b58decode(public_key_b58)
    vk = ecdsa.VerifyingKey.from_string(pub_bytes, curve=ecdsa.SECP256k1)
    try:
        vk.verify(base58.b58decode(signature_b58), message.encode())
        return True
    except ecdsa.BadSignatureError:
        return False 