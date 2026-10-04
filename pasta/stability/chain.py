"""The launch mint rule as the chain applies it (issue #40, ``docs/SPEC.md`` section 7).

Nobody is given coins except the genesis credit. Every other coin is minted, or burned, by
this rule as payments happen:

* A **payment** is a finalized block with ``amount > 0`` between two different addresses.
  Zero-amount blocks (validation-only) and self-payments carry no mint and are not counted.
* Every ``period_payments`` payments close a **period**. At the boundary the median-size
  controller (:class:`pasta.stability.AnchoredSizeController`, the same object the simulator
  runs) compares the smoothed median payment with the declared target and decides one supply
  change for the next period, bounded by the cap.
* That change is the next period's **budget**. Each payment in the period receives
  ``budget * amount / previous period's flow`` on top of its amount (taken from it, for a
  burn), until the budget is spent. The budget is never exceeded, so a large payment after a
  quiet period cannot mint more than the period was allowed. Unspent budget lapses.

The rule is a pure function of the chain: :class:`ChainStability` is fed blocks in order by
the node when it finalizes them and by :func:`pasta.validation.chain.verify_chain` when it
replays them, and both must arrive at the same ``mint_amount`` for every block.

The hybrid rule's step decomposition (flow per holder) is not switched on at launch: its flow
reference cannot be learned from a ten-coin economy. The median-size signal with a declared
target, dust floor and cap is the part the simulations and the chain data support on its own.

Known limitation: the controller's arithmetic is floating point, rounded to base units at
each period boundary. Python nodes agree bit for bit; an independent implementation would
need the same IEEE-754 operations in the same order. A production rule needs fixed point.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from pasta.core.crypto import GENESIS_ADDRESS
from pasta.core.units import UNITS_PER_PASTA
from pasta.stability.controller import AnchoredSizeController


@dataclass(frozen=True)
class StabilityParams:
    """Consensus constants of the mint rule. Amounts in base units."""

    genesis_supply: int = 10 * UNITS_PER_PASTA        # the only coins ever given: block 0
    target_median: int = 10 * UNITS_PER_PASTA         # declared, not learned: a typical payment is 10 PASTA
    period_payments: int = 10                         # payments per period
    alpha: float = 0.05                               # smoothing of the period median
    gain: float = 0.02                                # share of the relative gap closed per period
    cap_rate: float = 0.002                           # most the supply may change per period, mature chain
    bootstrap_cap_rate: float = 0.02                  # ... while the chain is small
    bootstrap_supply: int = 100_000 * UNITS_PER_PASTA # the bootstrap cap tapers above this supply
    dust_fraction: float = 0.05                       # payments below this share of the median are ignored


LAUNCH_PARAMS = StabilityParams()


def counts_as_payment(sender: str, receiver: str, amount: int) -> bool:
    return amount > 0 and sender != receiver and sender != GENESIS_ADDRESS


class ChainStability:
    """Replays the mint rule over a chain, one finalized block at a time."""

    def __init__(self, params: StabilityParams = LAUNCH_PARAMS) -> None:
        self.params = params
        u = float(UNITS_PER_PASTA)
        self._ctrl = AnchoredSizeController(
            anchor=params.target_median / u,
            alpha=params.alpha,
            gain=params.gain,
            cap_rate=params.cap_rate,
            bootstrap_cap_rate=params.bootstrap_cap_rate,
            bootstrap_supply=params.bootstrap_supply / u,
            dust_fraction=params.dust_fraction,
        )
        self.supply: int = 0
        self.periods: int = 0
        self.minted: int = 0
        self.burned: int = 0
        self._amounts: List[int] = []     # payments of the open period
        self._budget: int = 0             # supply change allotted to the open period (signed)
        self._remaining: int = 0          # part of the budget not yet dispensed (same sign)
        self._ref_flow: int = 0           # total paid in the previous period

    # ------------------------------------------------------------- the rule
    def mint_for(self, sender: str, receiver: str, amount: int) -> int:
        """Mint (positive) or burn (negative) for the next block, given the chain so far."""
        if not counts_as_payment(sender, receiver, amount) or self._remaining == 0 or self._ref_flow <= 0:
            return 0
        if self._budget > 0:
            return min(self._budget * amount // self._ref_flow, self._remaining)
        share = (-self._budget) * amount // self._ref_flow
        return -min(share, -self._remaining, amount)      # a burn cannot exceed the payment

    def smoothed_median(self) -> int:
        """The rule's statistic: smoothed median payment, in base units (0 before any period)."""
        return int(round((self._ctrl.stat or 0.0) * UNITS_PER_PASTA))

    def apply(self, block: Dict[str, Any]) -> None:
        """Advance the rule past a finalized block (block 0 included)."""
        sender = block.get("sender_address", "")
        receiver = block.get("receiver_address", "")
        amount = int(block.get("amount", 0))
        mint = int(block.get("mint_amount", 0))
        if sender == GENESIS_ADDRESS:
            self.supply += amount                 # genesis credit; the bootstrap block carries 0
        self.supply += mint
        if mint > 0:
            self.minted += mint
        else:
            self.burned -= mint
        if not counts_as_payment(sender, receiver, amount):
            return
        self._remaining -= mint
        self._amounts.append(amount)
        if len(self._amounts) >= self.params.period_payments:
            self._close_period()

    def _close_period(self) -> None:
        u = float(UNITS_PER_PASTA)
        self._ctrl.observe_period([a / u for a in self._amounts], 0, self.supply / u, None)
        self._budget = self._remaining = int(self._ctrl.last_delta * u)   # truncates toward zero
        self._ref_flow = sum(self._amounts)
        self._amounts = []
        self.periods += 1

    # ---------------------------------------------------------- diagnostics
    def status(self) -> Dict[str, Any]:
        u = float(UNITS_PER_PASTA)
        cap = self._ctrl.effective_cap(self.supply / u)
        return {
            "supply": self.supply,
            "genesis_supply": self.params.genesis_supply,
            "minted": self.minted,
            "burned": self.burned,
            "target_median": self.params.target_median,
            "smoothed_median": self.smoothed_median(),
            "signal": self._ctrl.signal(),
            "period": self.periods,
            "period_payments": self.params.period_payments,
            "payments_in_period": len(self._amounts),
            "period_budget": self._budget,
            "period_remaining": self._remaining,
            "cap_rate": cap,
        }


def replay(chain: List[Dict[str, Any]], params: StabilityParams = LAUNCH_PARAMS) -> ChainStability:
    """Rule state after every block of ``chain``."""
    state = ChainStability(params)
    for block in chain:
        state.apply(block)
    return state
