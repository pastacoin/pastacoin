# The fixed-supply test on other chains: does the *median* transaction track purchasing power?

Written 2026-09-27. Interactive version: https://pastacoin.org/results/chains.html.
Code: `pasta/analysis/chains.py`, `pasta/analysis/chains_report.py`. Data: `data/chains/*.csv`
(Blockchair daily transfer aggregates joined to CoinMetrics community series), committed.

## Why a second pass

`BITCOIN-COMPARISON.md` found that Bitcoin's *average* on-chain transaction grew 150x in
real terms, which breaks the whitepaper's gauge. But the average is dominated by exchange
and whale transfers. Blockchair publishes the daily **median** transfer value for every chain
it indexes, so the test can be repeated with a statistic that ordinary payments dominate.

Sources, all free and keyless:

- **Blockchair** `transactions?a=date,count(),sum(v),median(v),avg(v)`: for UTXO chains
  `v = output_total` (total outputs, so change is included; levels overstate true transfers,
  medians less so). For Ethereum `v = value` of plain ETH transfers with `value >= 0.001 ETH`,
  which drops zero-value contract calls but also ignores ERC-20 and stablecoin transfers.
  Bulk pulls trigger a temporary IP block; refresh one chain at a time.
- **CoinMetrics community CSV**: price, circulating supply, transaction count, active
  addresses, total fees, market cap.

Cleaning: monthly medians of daily values. A day whose median transfer is worth less than
$0.05 is dust (inscription spam, tipping bots) and is dropped from median metrics; the share
of such days is reported per year (Dogecoin 2024: 57 %, Bitcoin Cash 2019: 69 %).

## Results (elasticity = slope of log y on log x over the whole series)

| chain | years | price change | median coins/tx vs price | median USD/tx vs price | median share of supply vs users | reading |
|---|---|---|---|---|---|---|
| Litecoin | 2013 to 2026 | x20 | **-0.96** (r² 0.59) | **+0.04** (r² 0.00) | -1.31 (r² 0.78) | the whitepaper's assumption holds |
| Dogecoin | 2014 to 2026 | x338 | -0.65 (r² 0.54) | +0.35 (r² 0.25) | -2.0 (r² 0.12) | holds loosely; tipping conventions and 2024 dust distort it |
| Bitcoin Cash | 2018 to 2026 | x1 | -0.12 (r² 0.00) | +0.88 (r² 0.09) | -0.10 (r² 0.00) | no price range to test; dust-heavy |
| Ethereum | 2016 to 2026 | x203 | pending filtered pull | pending | pending | unfiltered medians are zero (contract calls) |
| Bitcoin | 2011 to 2026 | x20,000 | pending Blockchair medians | pending | pending | mean-based results in `BITCOIN-COMPARISON.md` |

Litecoin yearly median transaction in USD: 114, 271, 74, 96, 433, 159, 88, 56, 68, 169, 123,
133, 184, 154 (2013 to 2026). The price went from $2.7 to a $178 yearly median and back to
$55. The median transaction stayed within a factor of about three of $130 the whole time.

## What this says

1. **On a chain that was never capacity constrained, the median transaction tracked purchasing
   power almost exactly.** Litecoin's elasticity of -0.96 is the whitepaper's assumption
   ("real value per transaction is constant") observed over thirteen years and a 20x price
   move. This is the strongest empirical support the stability idea has so far.
2. **The mean is the wrong statistic.** Bitcoin's mean rose 150x in real terms; Litecoin's mean
   also swung by orders of magnitude (up to $30,000 in 2022) while its median sat near $100.
   Any signal PaSta reads must be a robust statistic of transaction size, not the average.
   The whitepaper says "average"; it should say "median" or a trimmed mean.
3. **Dust and conventions are the noise floor.** Inscription waves (Dogecoin 2024, Bitcoin
   Cash 2019 to 2020, Litecoin in a few months) push the daily median toward zero; tipping
   habits pinned Dogecoin's median at exactly 10,000 DOGE for three years. A live controller
   needs a dust floor and should expect step changes from conventions, not just from prices.
4. **The 1/users slope is noisier for medians than for means.** Litecoin gives -1.3 with a
   good fit; Dogecoin and Bitcoin Cash give nothing usable, because active addresses on those
   chains are dominated by bots and exchanges rather than people.

## Consequences for the simulator and the design

- Re-run the granularity and shock experiments with median-based controllers
  (`pasta/stability`) instead of EMA-of-amount controllers. The median is immune to a few
  large transactions but not to a shift in what a typical transaction is, so the granularity
  problem remains a design question; the evidence here says such shifts were small on
  payment-style chains and large on chains that became settlement layers.
- Keep the supply-rate cap (issue #28) regardless; Bitcoin shows how far a nominal gauge can
  drift when the network's role changes.

## Follow-ups

- Complete the Bitcoin median and filtered Ethereum pulls (Blockchair rate limits).
- Add Monero-style chains only if amounts are public (they are not).
- Consider a trimmed-mean or dust-filtered aggregate at fetch time (`q=output_total(10000..)`).
- Figures: `docs/figures/chains-*.png`; regenerate with
  `python -m pasta.analysis.chains_report --figures docs/figures`.
