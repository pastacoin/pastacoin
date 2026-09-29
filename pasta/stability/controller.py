"""Mint/burn policies.

Round one (per-transaction, sized as a fraction of the carrier transaction):

* :class:`FixedTargetController` - hold the EMA of transaction size at an absolute target.
* :class:`TrendController` - fast vs slow moving average of transaction size; the whitepaper
  rule read literally. Cannot hold a level, only slow a change.

Round two (per-period, sized as a fraction of the money supply, rate-capped; see
``docs/SIMULATION-RESULTS.md``). These need the economy to call
:meth:`observe_period` once per period with that period's transactions, active users and
money supply; the adjustment for the *next* period is then dispensed evenly across its
transactions by :meth:`adjust`, independent of each transaction's own size (issue #28).

* :class:`AnchoredSizeController` - signal is the period's **median** transaction size
  against an anchor fixed at launch (the whitepaper signal with the statistic the chain
  data says to use).
* :class:`FlowPerUserController` - signal is nominal flow per active user against an
  anchor that may grow by a fixed allowance per period. Immune to granularity shifts by
  construction; blind to per-capita real growth beyond the allowance (issue #27).

Both carry ``cap_rate``: the largest change in money supply per period, as a fraction of
supply. It bounds the damage of any misreading.

Lessons from the attack runs (see the memo) baked in as defaults:

* ``dispense="proportional"``: the period's supply change is shared across the next period's
  transactions in proportion to their amounts. Dispensing it *evenly* per transaction hands
  almost all of it to whoever spams the most transactions (sybil dust harvested 95 % of the
  mint). Proportional dispensing keeps the total change fixed by the signal, so it does not
  reintroduce the carrier-size bias of round one.
* ``dust_fraction``: amounts below this fraction of the running median transaction size are
  ignored when computing the statistic, so dust spam cannot drag the median.
* ``users="holders"`` for the flow rule: the user count is the number of addresses holding at
  least a fraction of a typical payment, supplied by the economy, rather than the number of
  addresses active in the period. Active-address counts rise and fall with transaction
  frequency, which made the flow rule as granularity-sensitive as the size rule.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import List, Optional, Protocol, runtime_checkable


@runtime_checkable
class Controller(Protocol):
    def adjust(self, amount: float) -> float:
        """Return mint (>0) or burn (<0) to apply to a transaction of ``amount``.

        Must be called once per admitted transaction, in order; controllers keep state.
        """

    def signal(self) -> float:
        """Diagnostic: current inflation estimate (>0 means the signal is running high)."""


@runtime_checkable
class PeriodAware(Protocol):
    def observe_period(self, amounts: List[float], active_users: int, money_supply: float,
                       holders: Optional[int] = None) -> None:
        """Called by the economy at the end of every period (step)."""


def _ema(prev: float | None, x: float, alpha: float) -> float:
    return x if prev is None else prev + alpha * (x - prev)


# ------------------------------------------------------------ round one ----

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


# ------------------------------------------------------------ round two ----

@dataclass
class _PeriodController:
    """Shared machinery: anchor learned at launch, EMA-smoothed statistic, supply-fraction
    sizing, rate cap, even dispensing over next period's transactions."""

    anchor: Optional[float] = None    # None: learn as the mean statistic over the first `learn_periods`
    learn_periods: int = 200
    alpha: float = 0.05               # EMA smoothing of the period statistic
    gain: float = 0.002               # fraction of the relative gap closed per period, as a share of M
    cap_rate: Optional[float] = 0.002 # max |ΔM| per period as a fraction of M; None = uncapped
    growth_per_period: float = 0.0    # anchor drift per period (allowance for real growth)
    asymmetric: bool = False          # mint only into above-median txs, burn only from below-median
    dispense: str = "proportional"    # "proportional" to amount, or "even" per transaction
    dust_fraction: float = 0.05       # ignore amounts below this fraction of the running median tx size
    stat: float | None = field(default=None, init=False)
    periods: int = field(default=0, init=False)
    _learn: List[float] = field(default_factory=list, init=False)
    _per_tx: float = field(default=0.0, init=False)        # even dispensing: adjustment per tx
    _scale: float = field(default=0.0, init=False)         # proportional dispensing: adjustment per unit amount
    _median: float = field(default=0.0, init=False)
    _last_delta: float = field(default=0.0, init=False)

    # subclasses override
    def _statistic(self, amounts: List[float], active_users: int, money_supply: float, holders: Optional[int]) -> Optional[float]:
        raise NotImplementedError

    def _clean(self, amounts: List[float]) -> List[float]:
        """Drop dust: amounts below ``dust_fraction`` of the running median transaction size."""
        floor = self.dust_fraction * (self._median or 0.0)
        return [a for a in amounts if a >= floor] if floor > 0 else list(amounts)

    def current_anchor(self) -> Optional[float]:
        if self.anchor is None:
            return None
        return self.anchor * (1.0 + self.growth_per_period) ** max(0, self.periods - self.learn_periods)

    def signal(self) -> float:
        a = self.current_anchor()
        if self.stat is None or not a:
            return 0.0
        return (self.stat - a) / a

    def observe_period(self, amounts: List[float], active_users: int, money_supply: float,
                       holders: Optional[int] = None) -> None:
        self.periods += 1
        clean = self._clean(amounts)
        if clean:
            self._median = statistics.median(clean)
        x = self._statistic(clean, active_users, money_supply, holders)
        self._per_tx = self._scale = 0.0
        if x is None:
            return
        if self.anchor is None:
            self._learn.append(x)
            if len(self._learn) >= self.learn_periods:
                self.anchor = statistics.fmean(self._learn)
            self.stat = _ema(self.stat, x, self.alpha)
            return
        self.stat = _ema(self.stat, x, self.alpha)
        s = self.signal()
        delta = -self.gain * s * money_supply          # negative signal -> mint
        if self.cap_rate is not None:
            lim = self.cap_rate * money_supply
            delta = max(-lim, min(lim, delta))
        self._last_delta = delta
        share = 2.0 if self.asymmetric else 1.0        # only about half of next period's txs are eligible
        if self.dispense == "even":
            self._per_tx = share * delta / max(1, len(clean))
        else:
            flow = sum(clean)
            self._scale = share * delta / flow if flow > 0 else 0.0

    def adjust(self, amount: float) -> float:
        adj = self._per_tx if self.dispense == "even" else self._scale * amount
        if self.asymmetric and adj:
            eligible = amount >= self._median if adj > 0 else amount <= self._median
            if not eligible:
                return 0.0
        return adj


@dataclass
class AnchoredSizeController(_PeriodController):
    """Whitepaper signal with the median: period median transaction size vs launch anchor."""

    def _statistic(self, amounts, active_users, money_supply, holders):
        return statistics.median(amounts) if amounts else None


@dataclass
class FlowPerUserController:
    """Nominal flow per active user vs a launch anchor with a growth allowance."""

    anchor: Optional[float] = None
    learn_periods: int = 200
    alpha: float = 0.05
    gain: float = 0.002
    cap_rate: Optional[float] = 0.002
    growth_per_period: float = 0.0
    asymmetric: bool = False
    dispense: str = "proportional"
    dust_fraction: float = 0.05
    users: str = "holders"            # "holders" (balance-weighted count from the economy) or "active"

    def __post_init__(self):
        self._impl = _FlowImpl(anchor=self.anchor, learn_periods=self.learn_periods, alpha=self.alpha, gain=self.gain,
                               cap_rate=self.cap_rate, growth_per_period=self.growth_per_period, asymmetric=self.asymmetric,
                               dispense=self.dispense, dust_fraction=self.dust_fraction, users=self.users)

    def observe_period(self, amounts, active_users, money_supply, holders=None):
        self._impl.observe_period(amounts, active_users, money_supply, holders)

    def adjust(self, amount: float) -> float:
        return self._impl.adjust(amount)

    def signal(self) -> float:
        return self._impl.signal()

    @property
    def stat(self):
        return self._impl.stat

    def current_anchor(self):
        return self._impl.current_anchor()


@dataclass
class _FlowImpl(_PeriodController):
    users: str = "holders"

    def _statistic(self, amounts, active_users, money_supply, holders):
        n = holders if (self.users == "holders" and holders is not None) else active_users
        if not amounts or not n or n <= 0:
            return None
        return sum(amounts) / n


def make_controller(name: str, **kwargs) -> Controller:
    name = name.lower()
    if name in ("null", "none", "off"):
        return NullController()
    if name in ("fixed", "target", "fixed-target"):
        return FixedTargetController(**kwargs)
    if name in ("trend", "whitepaper"):
        return TrendController(**kwargs)
    if name in ("size", "median", "anchored-size"):
        return AnchoredSizeController(**kwargs)
    if name in ("flow", "flow-user", "flow_user"):
        return FlowPerUserController(**kwargs)
    raise ValueError(f"unknown controller {name!r}; choose null, fixed, trend, size or flow")
