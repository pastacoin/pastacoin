# The fixed-supply test on other chains: does the *median* transaction track purchasing power?

Written 2026-09-27. Interactive version: https://pastacoin.org/results/chains.html.
Code: `pasta/analysis/chains.py`, `pasta/analysis/chains_report.py`. Data: `data/chains/*.csv`,
committed. Figures: `docs/figures/chains-*.png`.

## Why a second pass

`BITCOIN-COMPARISON.md` found that Bitcoin's *average* on-chain transaction grew 150x in
real terms, which breaks the whitepaper's gauge. But the average is dominated by exchange
and whale transfers. Daily **median** transaction values are published for every major chain,
so the test can be repeated with a statistic that ordinary payments dominate.

Sources, all free and keyless:

- **Blockchair** `transactions?a=date,count(),sum(v),median(v),avg(v)` for Litecoin,
  Dogecoin and Bitcoin Cash (`v = output_total`, so change outputs are included; levels
  overstate true transfers, medians much less so). Bulk pulls trigger a temporary IP block,
  which is why Bitcoin and Ethereum come from the second source.
- **BitInfoCharts** `mediantransactionvalue-<coin>.html` and `transactionvalue-<coin>.html`
  for Bitcoin and Ethereum: daily median and mean transaction value in USD, converted to coin
  units at the CoinMetrics daily price. Cross-check on Litecoin, where both sources exist:
  yearly medians agree within about 20 % (2016: $106 vs $96; 2022: $172 vs $169; 2026: $148 vs $154).
- **CoinMetrics community CSV**: price, circulating supply, transaction count, active
  addresses, total fees, market cap.

Cleaning: monthly medians of daily values. A day whose median transfer is worth less than
$0.05 is dust (inscription spam, tipping bots) and is dropped from median metrics; the share
of such days is reported per year (Dogecoin 2024: 57 %, Bitcoin Cash 2019: 69 %).

## Results (elasticity = slope of log y on log x over the whole series)

| chain | years | price | median coins/tx vs price | median USD/tx vs price | median USD/tx first, peak, last year | reading |
|---|---|---|---|---|---|---|
| Bitcoin | 2011 to 2026 | x23,000 | **-0.80** (r² 0.85) | +0.20 (r² 0.27) | $63, $795 (2021), $68 | holds, distorted by fee pressure 2017 to 2022 |
| Litecoin | 2013 to 2026 | x20 | **-0.96** (r² 0.59) | **+0.04** (r² 0.00) | $114, $433 (2017), $154 | holds cleanly |
| Dogecoin | 2014 to 2026 | x338 | -0.65 (r² 0.54) | +0.35 (r² 0.25) | $7, $432 (2021), $30 | holds loosely; conventions and dust distort |
| Bitcoin Cash | 2018 to 2026 | x1 | -0.12 (r² 0.00) | +0.88 (r² 0.09) | $111, $133 (2024), $105 | no price range to test; dust-heavy |
| Ethereum (plain ETH transfers >= 0.001 ETH) | 2016 to 2026 | x200 | -0.55 (r² 0.76) | +0.45 (r² 0.69) | $12, $243 (2021), $63 | half-tracks; not a payments chain, see below |

Bitcoin yearly median transaction in USD, 2011 to 2026: 63, 20, 68, 110, 81, 138, 400, 400,
232, 465, 795, 501, 99, 110, 177, 68. The mean over the same years went from $291 to
$118,659.

## What this says

1. **The whitepaper's assumption holds for the median on payment-style chains.** Litecoin's
   elasticity of -0.96 and Bitcoin's -0.80 mean that coins per typical transaction fell
   almost as fast as the price rose, over 13 to 15 years and price moves of 20x and 23,000x.
   The real value of a typical transaction stayed in a band of roughly $50 to $200 on both
   chains except during Bitcoin's 2017 to 2022 fee squeeze. This is the strongest empirical
   support the stability idea has: the signal the whitepaper wants to read exists, and it is
   the median, not the mean.
2. **The mean is the wrong statistic.** Bitcoin's mean rose 150x (change-adjusted) to 400x
   (raw) in real terms while its median ended where it started. Litecoin's mean reached
   $30,000 in 2022 while its median sat near $170. Any signal PaSta reads must be a robust
   statistic. The whitepaper says "average"; it should say "median" or a trimmed mean.
3. **Fee pressure is the main distortion, and it is visible.** Bitcoin's median USD size rose
   to $400 to $800 exactly in the years fees per transaction were in dollars (2017 to 2022)
   and fell back to about $100 when they eased. When block space is scarce, small payments
   leave the chain and the median of what remains rises. A chain that is never full should
   see less of this; Litecoin, which never was, shows the flattest median.
4. **Ethereum half-tracks, for structural reasons.** The unfiltered median is zero because most
   transactions are contract calls carrying no ETH, so the analysis uses Blockchair's
   aggregate over plain transfers of at least 0.001 ETH. That median went from $12 (2016) to
   $100 (2017), fell to $24 to $61 through 2020, peaked at $243 in 2021 and ended at $63 in
   2026: x5.4 in real terms while the price rose 200x. Elasticity of median ETH per transfer
   to price is -0.55, so about half of a price rise shows up as smaller transfers and half as
   larger real transfers. Plain ETH transfers are mostly exchange deposits and gas top-ups;
   the payment activity lives in ERC-20 stablecoins that none of these statistics see. It is
   a platform's settlement layer, not a currency, and its result sits between Bitcoin's mean
   and Bitcoin's median for that reason.
5. **Dust and conventions are the noise floor.** Inscription waves push daily medians toward
   zero; Dogecoin's median sat at exactly 10,000 DOGE for three years because of tipping
   habits. A live controller needs a dust floor and should expect step changes from
   conventions as well as prices.
6. **The 1/users slope is noisier for medians than for means.** Litecoin gives -1.3 with a
   good fit, Bitcoin -1.8 (r² 0.69), Dogecoin and Bitcoin Cash nothing usable, because active
   addresses on those chains are dominated by bots and exchanges rather than people.

## Consequences for the simulator and the design

- Re-run the granularity and shock experiments with median-based controllers in
  `pasta/stability`. The median is immune to a few large transactions but not to a shift in
  what a typical transaction is; the evidence here says such shifts were small on
  payment-style chains and were driven by fees when they happened.
- Keep the supply-rate cap (issue #28) regardless; Bitcoin's mean shows how far a nominal
  gauge can drift when the network's role changes.
- The whitepaper's Bitcoin appendix should be rewritten around the median series with the
  supply adjustment, and should name fee pressure as the known distortion.

## Follow-ups

- Blockchair medians for Bitcoin as a second source, for the same cross-check done on
  Litecoin (a single aggregate request re-triggered the rate limit on 2026-09-27).
- Dust-filtered aggregates at fetch time (`q=output_total(10000..)`).
