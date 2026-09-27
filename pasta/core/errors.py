"""Exceptions raised by the node when a request violates protocol rules.

Front-ends catch :class:`PastaError` and show ``str(exc)`` to the user; the REST
layer maps it to HTTP 400.
"""


class PastaError(Exception):
    """Base class for all protocol-level rejections."""


class InvalidTransaction(PastaError):
    """Malformed transaction (bad amount, missing fields, duplicate id)."""


class InvalidSignature(PastaError):
    """Signature missing or does not verify against the sender address."""


class InsufficientBalance(PastaError):
    """Sender cannot cover the amount."""


class InvalidTransition(PastaError):
    """State machine rule violated (wrong state, self-validation, ...)."""


class NotFound(PastaError):
    """Referenced transaction is not in the mempool."""
