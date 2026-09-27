# PastaTester results memo (living document)

Findings from `python -m pasta.sim` about the whitepaper's stability mechanism. Each entry
records the exact command so it can be re-run. Numbers are for the default economy
(200 agents, 5000 steps, seed 1, money demand k = 20, purchase probability 0.10, mean real
price 1.0, lognormal sigma 0.6) unless stated. "Drift" is the change in the PASTA price
level `p` (PASTA per unit of real goods) from step 500 to the end; a flat `p` means constant
purchasing power. Model definition: docstring of `pasta/sim/economy.py`. Controllers:
docstring of `pasta/stability/controller.py`.

## 2026-09-27 — first pass: does the average-transaction-size rule hold purchasing power?

### Setup

Three policies compared under one shock at step 2000:

- `null`: no mint or burn (baseline).
- `trend`: the whitepaper rule read literally. Signal = fast EMA of tx size vs slow EMA.
  Mint only into above-average transactions when the average is falling; burn only from
  below-average transactions when it is rising. Gain 0.5, cap 10 % of the transaction.
- `fixed`: same asymmetric rule, but the signal is the EMA of tx size vs a fixed target
  equal to the launch-time average (50 PASTA here). Gain 0.1 unless stated.

Command shape: `python -m pasta.sim --controller <c> [--param target=50 --param gain=0.1] --shock 2000:<kind>:<factor>`

### Results (price-level drift, step 500 to 5000)

| Shock at step 2000 | What happens to purchasing power | null | trend (whitepaper literal) | fixed anchor at launch avg, gain 0.1 |
|---|---|---|---|---|
| none | nothing | 0.0 % | **+10.7 %** | -0.3 % |
| money demand x1.5 (hoarding) | falls 33 % | -33.3 % | -23.2 % | **+2.0 %** (recovers to within 5 % after ~2800 steps; gain 0.5 recovers in ~600 steps at the cost of 15x more burn churn) |
| money demand x0.67 (dishoarding) | rises 49 % | +49.3 % | +58.3 % | +17.2 % |
| per-capita real growth x2 | rises 100 % | -50.0 % | -39.1 % | **+0.4 %** (M grew +101 %) |
| adoption: +200 agents with no coins | rises 100 % | -50.0 % | -40.6 % | **+7.1 %** (M grew +114 %) |
| granularity x2: same real spending, half as many transactions each twice as large | **unchanged** | 0.0 % | -3.0 % | **-33.7 %** (self-inflicted) |
| granularity x0.5 | **unchanged** | 0.0 % | (not run) | **+100.8 %** (self-inflicted) |

Seeds 1 to 5 give the same picture (trend under hoarding: -23.2 % to -24.4 %).

### What this says

1. **A trend-only rule cannot restore purchasing power; it can only slow a change.** After a
   shock the slow average converges to the new level and the controller stops. It cut the
   hoarding shock from -33 % to -23 % and no more. The whitepaper's phrase "keep transaction
   sizes consistent over time" needs an anchor: a target average fixed at launch (or an
   extremely slow reference). With that anchor the rule does what the whitepaper claims for
   monetary shocks: hoarding, dishoarding, real growth and adoption were all brought back to
   within a few percent, and the money supply grew with the economy (+101 % for a 2x real
   economy, +114 % for 2x agents).

2. **The literal asymmetry rule is biased.** With no shock at all the asymmetric trend
   controller inflated the price level by 10.7 %, and a symmetric variant deflated it by
   45 %. Cause: mint and burn are sized as a fraction of the transaction they ride on.
   Mints attach to above-average (large) transactions and burns to below-average (small)
   ones, so mints outweigh burns for the same signal; the symmetric version has the
   opposite bias because burns happen when prices are high (amounts large). Any final rule
   must size adjustments independently of the carrier transaction, or normalise them, before
   the asymmetry can be trusted as an anti-manipulation device. Follow-up issue filed.

3. **Granularity is the real threat, and the anchored rule makes it worse, not better.** If
   people move the same real spending into half as many transactions, purchasing power is
   unchanged but the average transaction size doubles. The anchored controller reads that as
   inflation and burns a third of the money supply (gain 0.1) — more with higher gain. The
   whitepaper argues such shifts are unlikely to be economy-wide; that may be true, but the
   controller has no way to tell a granularity shift from inflation because both raise the
   average. The trend controller is nearly immune only because it gives up after any level
   change, which is also why it is useless against real inflation. A signal that separates
   "prices rose" from "people batch purchases" is the central open design problem. Candidates
   to test next: nominal spending per active address per period (immune to granularity, but
   blind to per-capita real growth), transaction-count-weighted measures, and combinations.

4. **Gain trades recovery speed for churn.** Under hoarding with the anchored rule, gain 0.05
   never gets back within 5 % in 3000 steps, gain 0.1 takes ~2800 steps with almost no burn,
   gain 0.5 takes ~600 steps but burns 10.8k PASTA against 24.8k minted. Final drift is
   within 5 % for all of them. Low gain with long horizons looks preferable; the "small,
   continuous adjustments" language in the whitepaper points the same way.

5. **Deflationary side is weaker.** Dishoarding (k x0.67) ended +17 % with the anchored rule
   versus +2 % for the mirror-image hoarding case. The asymmetric rule only burns from
   below-average transactions and the burn cannot exceed the transaction, so the burn side
   has less capacity than the mint side.

### Model limitations to keep in mind

- With k = 20 and purchase probability 0.10 each agent holds about two purchases worth of
  money, so roughly 45 % of attempted purchases are skipped as unaffordable. This biases
  observed averages (larger purchases are skipped more) and damps nominal volume. Raising k
  reduces skips; the qualitative results above did not depend on it, but the numbers do.
- Sellers receive mint/burn; buyers always pay the face amount. The whitepaper describes the
  same direction (payer loses less than recipient gets) but the split is a free design choice.
- Price level is a closed-form quantity-theory expression, not an emergent market price.
  There are no expectations, no interest, no external exchange rate.
- No adversarial agents yet (self-dealing, wash trading); see issue #13.

### Next experiments

- Signal alternatives robust to granularity (per-address nominal spending, hybrid).
- Adjustment sizing independent of carrier transaction (fixed-size or supply-fraction).
- Attack models: an agent pair wash-trading to move the average; cost to attacker vs damage.
- Longer horizons and repeated shocks; k sweep to check sensitivity to the skip rate.
