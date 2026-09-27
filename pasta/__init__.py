"""Pasta package root.

Public API::

    from pasta import Node, generate_keypair, sign_transaction, PastaError
"""
from __future__ import annotations

from pasta.core.crypto import generate_keypair, public_key_for, sign_transaction  # noqa: F401
from pasta.core.errors import (  # noqa: F401
    InsufficientBalance,
    InvalidSignature,
    InvalidTransaction,
    InvalidTransition,
    NotFound,
    PastaError,
)
from pasta.node import Node  # noqa: F401
from pasta.validation.chain import verify_chain  # noqa: F401

__all__ = [
    "Node",
    "generate_keypair",
    "public_key_for",
    "sign_transaction",
    "verify_chain",
    "PastaError",
    "InvalidTransaction",
    "InvalidSignature",
    "InsufficientBalance",
    "InvalidTransition",
    "NotFound",
]
