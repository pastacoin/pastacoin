"""A deliberately small monetary economy in which PASTA is the only money.

Model
-----
* There is a **hidden real price level**. Goods have real prices ``r`` (in an abstract
  stable unit, think "loaves of bread"). Nobody in the economy can see this unit; the
  controller only ever sees PASTA amounts.
* The PASTA **price level** follows the quantity theory of money:
  ``p = M / (k * Q)`` where ``M`` is total PASTA held by agents, ``Q`` is the real volume of
  goods traded per step and ``k`` is money demand (how many steps of spending agents want
  to hold as balances; hoarding raises ``k``). A good with real price ``r`` therefore costs
  ``r * p`` PASTA. ``1/p`` is the purchasing power of one PASTA.
* Each step a fraction of agents buy one good from a random seller. Transaction amount in
  PASTA is ``r * p``. If the buyer cannot afford it the purchase is skipped (recorded).
* The **controller** sees each PASTA amount and returns a mint (credited to the seller in
  addition to the amount) or a burn (deducted from what the seller receives). Mint/burn
  changes ``M`` and therefore ``p`` on the next step. Buyers always pay exactly the amount.
* **Shocks** change the hidden economy at a given step:
  - ``money_demand`` multiplies ``k`` (hoarding). Purchasing power falls; the controller
    *should* offset it by minting.
  - ``volume`` multiplies each agent's purchase rate (real growth per capita); ``agents``
    adds newcomers with zero balance (adoption). Purchasing power rises; the controller
    should grow ``M`` to match. Nominal spending per step stays ``M / k`` in both cases,
    as the quantity theory requires.
  - ``granularity`` multiplies the real price per purchase by ``f`` and divides the purchase
    probability by ``f``: the same real spending in fewer, larger transactions (the
    whitepaper's "installments to lump sum" worry). Purchasing power is *unchanged*, but the
    average transaction size doubles, so a controller that trusts the average will wrongly
    burn. This is the adversarial shock for the whole thesis.
  - ``real_prices`` rescales the hidden unit. Under the quantity theory nothing observable
    changes (PASTA amounts per good are unchanged); it is a sanity check, and the
    ``price_level`` metric is meaningless for it.

What we measure: how far ``p`` drifts and how much it varies, with and without a
controller, under each shock. The thesis holds if the controller keeps ``p`` flatter than
the null baseline without amplifying real-price shocks.
"""
from __future__ import annotations

import csv
import random
import statistics
from dataclasses import asdict, dataclass, field
from typing import Iterable, List, Optional

from pasta.stability import Controller, NullController, make_controller


@dataclass
class Shock:
    step: int
    kind: str          # "money_demand" | "volume" | "agents" | "granularity" | "real_prices"
    factor: float      # multiply the target quantity by this (agents: add int(factor))

    @classmethod
    def parse(cls, text: str) -> "Shock":
        """Parse ``step:kind:factor`` e.g. ``2000:money_demand:1.5``."""
        step, kind, factor = text.split(":")
        return cls(int(step), kind, float(factor))


@dataclass
class SimConfig:
    agents: int = 200
    steps: int = 5000
    seed: int = 1
    controller: str = "null"
    controller_kwargs: dict = field(default_factory=dict)
    initial_balance: float = 100.0
    buy_probability: float = 0.10       # fraction of agents that attempt a purchase per step
    money_demand: float = 20.0          # k: steps of spending agents hold as balances
    real_price_mean: float = 1.0        # mean real price of a good (hidden unit)
    real_price_sigma: float = 0.6       # lognormal sigma of real prices
    shocks: List[Shock] = field(default_factory=list)
    warmup: int = 500                   # steps ignored when computing drift metrics


@dataclass
class StepRecord:
    step: int
    price_level: float
    money_supply: float
    avg_tx_pasta: float
    tx_volume_pasta: float
    tx_count: int
    minted: float
    burned: float
    skipped: int
    signal: float


class Economy:
    def __init__(self, cfg: SimConfig, controller: Optional[Controller] = None):
        self.cfg = cfg
        self.rng = random.Random(cfg.seed)
        self.controller: Controller = controller or make_controller(cfg.controller, **cfg.controller_kwargs)
        self.balances: List[float] = [cfg.initial_balance] * cfg.agents
        self.real_price_mean = cfg.real_price_mean
        self.buy_probability = cfg.buy_probability
        self.money_demand = cfg.money_demand
        self.records: List[StepRecord] = []
        self.total_minted = 0.0
        self.total_burned = 0.0
        self._shocks = sorted(cfg.shocks, key=lambda s: s.step)

    # ------------------------------------------------------------- model
    @property
    def money_supply(self) -> float:
        return sum(self.balances)

    def real_volume_per_step(self) -> float:
        """Expected real value traded per step (hidden unit)."""
        return len(self.balances) * self.buy_probability * self.real_price_mean

    def price_level(self) -> float:
        q = self.real_volume_per_step()
        return self.money_supply / (self.money_demand * q) if q > 0 else 0.0

    def _draw_real_price(self) -> float:
        # lognormal around the mean: mean of lognormal = exp(mu + sigma^2/2)
        sigma = self.cfg.real_price_sigma
        mu = -0.5 * sigma * sigma
        return self.real_price_mean * self.rng.lognormvariate(mu, sigma)

    def _apply_shocks(self, step: int) -> None:
        while self._shocks and self._shocks[0].step == step:
            s = self._shocks.pop(0)
            if s.kind == "real_prices":
                self.real_price_mean *= s.factor
            elif s.kind == "money_demand":
                self.money_demand *= s.factor
            elif s.kind == "volume":
                self.buy_probability = min(1.0, self.buy_probability * s.factor)
            elif s.kind == "granularity":
                self.real_price_mean *= s.factor
                self.buy_probability = min(1.0, self.buy_probability / s.factor)
            elif s.kind == "agents":
                n = int(s.factor)
                if n > 0:
                    self.balances.extend([0.0] * n)      # newcomers arrive with nothing
                elif n < 0:
                    # leavers take their money with them (money destroyed from this economy)
                    for _ in range(min(-n, len(self.balances) - 1)):
                        self.balances.pop(self.rng.randrange(len(self.balances)))
            else:
                raise ValueError(f"unknown shock kind {s.kind!r}")

    # -------------------------------------------------------------- step
    def step(self, t: int) -> StepRecord:
        self._apply_shocks(t)
        p = self.price_level()
        n = len(self.balances)
        amounts: List[float] = []
        minted = burned = 0.0
        skipped = 0
        buyers = [i for i in range(n) if self.rng.random() < self.buy_probability]
        for buyer in buyers:
            seller = self.rng.randrange(n)
            if seller == buyer:
                continue
            amount = self._draw_real_price() * p
            if amount <= 0:
                continue
            if self.balances[buyer] + 1e-12 < amount:
                skipped += 1
                continue
            adj = self.controller.adjust(amount)
            credit = amount + adj
            if credit < 0:          # a burn cannot exceed the payment
                adj = -amount
                credit = 0.0
            self.balances[buyer] -= amount
            self.balances[seller] += credit
            amounts.append(amount)
            if adj > 0:
                minted += adj
            else:
                burned += -adj
        self.total_minted += minted
        self.total_burned += burned
        rec = StepRecord(
            step=t,
            price_level=p,
            money_supply=self.money_supply,
            avg_tx_pasta=statistics.fmean(amounts) if amounts else 0.0,
            tx_volume_pasta=sum(amounts),
            tx_count=len(amounts),
            minted=minted,
            burned=burned,
            skipped=skipped,
            signal=self.controller.signal(),
        )
        self.records.append(rec)
        return rec

    def run(self) -> "Economy":
        for t in range(self.cfg.steps):
            self.step(t)
        return self

    # ----------------------------------------------------------- metrics
    def recovery_steps(self, tolerance: float = 0.05, hold: int = 100) -> Optional[int]:
        """Steps after the first shock until the price level stays within ``tolerance`` of its
        pre-shock value for ``hold`` consecutive steps. None if it never does (or no shock)."""
        if not self.cfg.shocks:
            return None
        t0 = min(s.step for s in self.cfg.shocks)
        if t0 <= 0 or t0 >= len(self.records):
            return None
        p_pre = self.records[t0 - 1].price_level
        if not p_pre:
            return None
        run = 0
        for r in self.records[t0:]:
            run = run + 1 if abs(r.price_level / p_pre - 1.0) <= tolerance else 0
            if run >= hold:
                return r.step - t0 - hold + 1
        return None

    def metrics(self) -> dict:
        recs = [r for r in self.records if r.step >= self.cfg.warmup]
        if len(recs) < 2:
            recs = self.records
        p = [r.price_level for r in recs]
        p0 = p[0] if p and p[0] else 1.0
        rel = [x / p0 for x in p]
        return {
            "recovery_steps": self.recovery_steps(),
            "controller": self.cfg.controller,
            "steps": self.cfg.steps,
            "final_price_level": p[-1] if p else 0.0,
            "price_drift_pct": (rel[-1] - 1.0) * 100.0 if rel else 0.0,
            "price_max_dev_pct": (max(abs(x - 1.0) for x in rel)) * 100.0 if rel else 0.0,
            "price_stdev_pct": statistics.pstdev(rel) * 100.0 if len(rel) > 1 else 0.0,
            "money_supply_change_pct": (recs[-1].money_supply / recs[0].money_supply - 1.0) * 100.0 if recs and recs[0].money_supply else 0.0,
            "total_minted": self.total_minted,
            "total_burned": self.total_burned,
            "skipped_purchases": sum(r.skipped for r in self.records),
            "transactions": sum(r.tx_count for r in self.records),
        }

    def write_csv(self, path: str) -> None:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(asdict(self.records[0]).keys()))
            w.writeheader()
            for r in self.records:
                w.writerow(asdict(r))


def run_simulation(cfg: SimConfig, controller: Optional[Controller] = None) -> Economy:
    return Economy(cfg, controller).run()


def compare(cfgs: Iterable[SimConfig]) -> List[dict]:
    return [run_simulation(c).metrics() for c in cfgs]
