"""Basic crypto helpers using ecdsa + base58 (prototype only)."""
import ecdsa, base58

def generate_keypair() -> dict:
    """Generate secp256k1 keypair, return dict with private_key and public_key (base58)."""
    priv = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1)
    pub = priv.get_verifying_key()
    priv_b58 = base58.b58encode(priv.to_string()).decode()
    pub_b58 = base58.b58encode(pub.to_string()).decode()
    return {"private_key": priv_b58, "public_key": pub_b58} 