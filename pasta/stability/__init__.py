"""Stability controllers: decide how much to mint or burn on each transaction.

A controller is a pure policy object. It sees each transaction amount in order and
returns the mint (positive) or burn (negative) to apply to that transaction. The same
objects drive :mod:`pasta.sim` today and will drive :class:`pasta.node.Node` once the
simulation says which rule holds up.
"""

from pasta.stability.controller import (  # noqa: F401
    Controller,
    FixedTargetController,
    NullController,
    TrendController,
    make_controller,
)

__all__ = ["Controller", "NullController", "FixedTargetController", "TrendController", "make_controller"]
