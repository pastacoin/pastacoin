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
    bootstrap_cap_rate: Optional[float] = None  # looser cap while supply is small (launch rule); None = off
    bootstrap_supply: float = 0.0     # at or below this supply the bootstrap cap applies in full; above it
                                      # the cap falls as bootstrap_supply / M until it meets cap_rate
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

    def effective_cap(self, money_supply: float) -> Optional[float]:
        """The cap in force at this supply: ``cap_rate``, raised by the bootstrap schedule."""
        if self.cap_rate is None or not self.bootstrap_cap_rate or money_supply <= 0:
            return self.cap_rate
        boot = self.bootstrap_cap_rate * min(1.0, self.bootstrap_supply / money_supply)
        return max(self.cap_rate, boot)

    @property
    def last_delta(self) -> float:
        """Supply change decided at the last period boundary (after the cap)."""
        return self._last_delta

    def observe_period(self, amounts: List[float], active_users: int, money_supply: float,
                       holders: Optional[int] = None) -> None:
        self.periods += 1
        self._last_delta = 0.0
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
        cap = self.effective_cap(money_supply)
        if cap is not None:
            lim = cap * money_supply
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


@dataclass
class HybridController(_PeriodController):
    """Median-size signal with a flow-per-holder step decomposition (issue #37).

    Two things the chain can see move together under a monetary shock (hoarding, adoption)
    and apart under a structural one (a change in payment granularity): the median payment
    and nominal flow per holder. This controller normally acts on the median-size signal.
    When the median takes a **step** (its fast EMA leaves a slow reference by more than
    ``step_threshold``) it enters step mode: while the step plays out it acts on the flow
    signal (flow per holder against its own launch anchor, the monetary part), and once the
    median has settled (``settle_periods`` periods within ``settle_tolerance``) it re-anchors
    the median to the level consistent with the current flow signal, so that whatever part of
    the step flow did not explain is treated as structure, and returns to the size signal.
    Slow drifts (steady real growth) never look like a step and pass straight through, which
    is how the size rule tracks growth without an allowance.

    The flow reference itself drifts slowly toward observed flow per holder, but only while the
    size signal is near zero and no step is open: after growth has been matched by minting,
    flow per holder is legitimately higher; during a recovery it must not be re-based.

    Consequence: a sudden real-growth doubling is misread as structural (accepted: real growth
    does not double overnight); a granularity shift during hoarding is split into a re-anchor
    and a mint.
    """

    step_threshold: float = 0.15    # fast/slow deviation of the median that opens step mode
    slow_alpha: float = 0.005       # slow reference EMA (frozen during a step)
    settle_periods: int = 30        # step is over when the fast median stays within tolerance this long
    settle_tolerance: float = 0.05
    users: str = "holders"
    flow_anchor: Optional[float] = None   # learned with the size anchor unless given
    calm_tolerance: float = 0.15          # |size signal| below this and no step: flow reference may drift
    fast_m: float | None = field(default=None, init=False)
    slow_m: float | None = field(default=None, init=False)
    fast_f: float | None = field(default=None, init=False)
    slow_f: float | None = field(default=None, init=False)
    in_step: bool = field(default=False, init=False)
    reanchors: int = field(default=0, init=False)
    last_structural: float = field(default=0.0, init=False)
    _hist: List[float] = field(default_factory=list, init=False)
    _learn_f: List[float] = field(default_factory=list, init=False)

    def flow_signal(self) -> Optional[float]:
        if self.fast_f is None or not self.flow_anchor:
            return None
        return self.fast_f / self.flow_anchor - 1.0

    def _statistic(self, amounts, active_users, money_supply, holders):
        if not amounts:
            return None
        med = statistics.median(amounts)
        n = holders if (self.users == "holders" and holders is not None) else active_users
        flow = sum(amounts) / n if n else None
        self.fast_m = _ema(self.fast_m, med, self.alpha)
        if flow is not None:
            self.fast_f = _ema(self.fast_f, flow, self.alpha)
        if not self.in_step:
            self.slow_m = _ema(self.slow_m, med, self.slow_alpha)
        if self.anchor is None:
            if flow is not None and self.flow_anchor is None:
                self._learn_f.append(flow)
                if len(self._learn_f) >= self.learn_periods:
                    self.flow_anchor = statistics.fmean(self._learn_f)
            return med
        if not self.slow_m or self.flow_signal() is None:
            return med
        js = self.fast_m / self.slow_m - 1.0
        if not self.in_step and abs(js) > self.step_threshold:
            self.in_step = True
            self._hist = []
        # Real growth raises flow per holder permanently while the median sits at its anchor
        # (the size rule has minted to match). Let the flow reference follow, but only when
        # nothing else is going on, so a step or a recovery in progress never re-bases it.
        if not self.in_step and abs(super().signal()) < self.calm_tolerance:
            self.flow_anchor = _ema(self.flow_anchor, self.fast_f, self.slow_alpha)
        if self.in_step:
            self._hist.append(self.fast_m)
            self._hist = self._hist[-self.settle_periods:]
            settled = (len(self._hist) >= self.settle_periods
                       and max(self._hist) / min(self._hist) - 1.0 < self.settle_tolerance)
            if settled:
                # the median level consistent with the current monetary state
                consistent = self.fast_m / (1.0 + self.flow_signal())
                structural = consistent / self.anchor - 1.0
                self.last_structural = structural
                if abs(structural) > 1e-9:
                    self.anchor = consistent
                    self.reanchors += 1
                self.slow_m = self.fast_m
                self.in_step = False
                self._hist = []
        return med

    def signal(self) -> float:
        fs = self.flow_signal()
        if self.in_step and fs is not None:
            return fs                                   # monetary part only, during a step
        return super().signal()


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
    if name in ("hybrid", "size+flow"):
        return HybridController(**kwargs)
    raise ValueError(f"unknown controller {name!r}; choose null, fixed, trend, size, flow or hybrid")
