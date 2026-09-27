"""Mint/burn policies driven by the average transaction size.

Whitepaper rule (PaSta Description, "Passive Stability Mechanism"): the network-wide
average transaction amount is the inflation signal. A rising average suggests inflation
(burn), a falling one deflation (mint). To blunt self-dealing, mint only into
transactions *above* the current average and burn only from transactions *below* it.

Two readings of "the average is trending" are implemented:

* :class:`FixedTargetController` - hold the average at an absolute target. Simple, but
  the target is arbitrary and the whitepaper does not really ask for it.
* :class:`TrendController` - compare a fast moving average with a slow one. No absolute
  anchor; it fights *changes* in the average, which is the whitepaper's actual claim.

Both scale the adjustment by ``gain`` and cap it at ``max_fraction`` of the transaction.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class Controller(Protocol):
    def adjust(self, amount: float) -> float:
        """Return mint (>0) or burn (<0) to apply to a transaction of ``amount``.

        Must be called once per admitted transaction, in order; controllers keep state.
        """

    def signal(self) -> float:
        """Diagnostic: current inflation estimate (>0 means the average is running high)."""


def _ema(prev: float | None, x: float, alpha: float) -> float:
    return x if prev is None else prev + alpha * (x - prev)


@dataclass
class NullController:
    """No mint, no burn. The baseline every other controller is compared against."""

    def adjust(self, amount: float) -> float:
        return 0.0

    def signal(self) -> float:
        return 0.0


@dataclass
class FixedTargetController:
    target: float = 10.0
    alpha: float = 0.01          # EMA smoothing of the observed average
    gain: float = 0.5            # fraction of the gap to close per transaction
    max_fraction: float = 0.10   # never adjust more than this fraction of the amount
    asymmetric: bool = True      # whitepaper rule: mint only above avg, burn only below
    avg: float | None = field(default=None, init=False)

    def signal(self) -> float:
        if self.avg is None or self.target <= 0:
            return 0.0
        return (self.avg - self.target) / self.target

    def adjust(self, amount: float) -> float:
        self.avg = _ema(self.avg, amount, self.alpha)
        s = self.signal()
        adj = 0.0
        if s < 0 and (not self.asymmetric or amount >= self.avg):
            adj = min(-s * self.gain, self.max_fraction) * amount       # deflation: mint
        elif s > 0 and (not self.asymmetric or amount <= self.avg):
            adj = -min(s * self.gain, self.max_fraction) * amount       # inflation: burn
        return adj


@dataclass
class TrendController:
    fast_alpha: float = 0.05
    slow_alpha: float = 0.002
    gain: float = 0.5
    max_fraction: float = 0.10
    asymmetric: bool = True
    fast: float | None = field(default=None, init=False)
    slow: float | None = field(default=None, init=False)

    def signal(self) -> float:
        if self.fast is None or self.slow is None or self.slow <= 0:
            return 0.0
        return (self.fast - self.slow) / self.slow

    def adjust(self, amount: float) -> float:
        self.fast = _ema(self.fast, amount, self.fast_alpha)
        self.slow = _ema(self.slow, amount, self.slow_alpha)
        s = self.signal()
        adj = 0.0
        if s < 0 and (not self.asymmetric or amount >= self.fast):
            adj = min(-s * self.gain, self.max_fraction) * amount
        elif s > 0 and (not self.asymmetric or amount <= self.fast):
            adj = -min(s * self.gain, self.max_fraction) * amount
        return adj


def make_controller(name: str, **kwargs) -> Controller:
    name = name.lower()
    if name in ("null", "none", "off"):
        return NullController()
    if name in ("fixed", "target", "fixed-target"):
        return FixedTargetController(**kwargs)
    if name in ("trend", "whitepaper"):
        return TrendController(**kwargs)
    raise ValueError(f"unknown controller {name!r}; choose null, fixed or trend")
