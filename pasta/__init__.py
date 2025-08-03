from __future__ import annotations

"""Pasta package root.

This package exposes the core public API so that external tools can simply do::

    from pasta import Node, generate_keypair

and be frontend-agnostic.
"""

from pasta.node import Node
from pasta.core.crypto import generate_keypair  # re-export

__all__ = ["Node", "generate_keypair"]
 