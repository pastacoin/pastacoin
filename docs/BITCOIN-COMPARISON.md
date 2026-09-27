# Bitcoin as a fixed-supply economy: the whitepaper chart, rebuilt and corrected

Written 2026-09-27. Interactive version: https://pastacoin.org/results/bitcoin.html.
Code: `pasta/analysis/bitcoin.py` (data and metrics), `pasta/analysis/bitcoin_report.py`
(figures and site data). Data: `data/bitcoin-daily.csv`, a slim daily extract of the
blockchain.com charts API (price, confirmed transactions, estimated transaction volume in BTC
and USD, coins in circulation, unique addresses, fees) committed for reproducibility;
refresh with `python -m pasta.analysis.bitcoin_report --fetch`.

## The claim being tested

The whitepaper's appendix uses Bitcoin to argue that in a fixed-supply currency a growing
economy shows up as shrinking transaction sizes, and that the average transaction size is
therefore a usable purchasing-power gauge. It shows price rising from under $100 to over
$100,000 while the average transaction fell from 10 to 20 BTC to under 1 BTC, and notes that
the effect is understated because supply grew and because block-space limits pushed small
transactions off chain.

## The coarse model

Fixed supply M. N users who each hold about the same real money balance and make about the same
real purchases. Quantity theory then says price per coin is proportional to N and coins per
transaction are proportional to 1/N. On log-log axes, coins per transaction against users is a
straight line of slope -1. That is the entire model; `fixed_supply_toy()` renders it.

## What the data shows (yearly medians of daily values)

| year | price $ | supply M | tx/day | addresses/day | BTC/tx | ppm of supply/tx | USD/tx | fee $/tx |
|---|---|---|---|---|---|---|---|---|
| 2011 | 4 | 6.7 | 5,374 | 9,810 | 19.27 | 2.960 | 75 | 0.00 |
| 2013 | 112 | 11.4 | 52,979 | 60,282 | 4.25 | 0.369 | 442 | 0.09 |
| 2016 | 580 | 15.7 | 224,275 | 398,490 | 1.23 | 0.079 | 680 | 0.16 |
| 2017 | 2,558 | 16.4 | 282,917 | 548,402 | 0.90 | 0.055 | 2,645 | 2.33 |
| 2021 | 47,834 | 18.7 | 270,736 | 679,752 | 0.39 | 0.021 | 18,117 | 5.09 |
| 2024 | 64,100 | 19.7 | 508,934 | 536,188 | 0.22 | 0.011 | 13,490 | 3.22 |
| 2026 | 71,130 | 20.0 | 582,412 | 481,546 | 0.16 | 0.008 | 11,171 | 0.36 |

2011 to 2026: price x20,000, market cap x56,000, supply x3, BTC per transaction divided by
120, share of supply per transaction divided by 370, USD per transaction x150.

Elasticities (slope of log y on log x, monthly medians):

| era | BTC/tx vs price | USD/tx vs price | share of supply vs active addresses | share vs market cap | median fee/tx |
|---|---|---|---|---|---|
| 2011 to 2016 | -0.47 (r² 0.91) | +0.54 (r² 0.93) | **-0.87 (r² 0.94)** | -0.53 | $0.06 |
| 2017 to 2026 | -0.33 (r² 0.59) | +0.67 (r² 0.86) | +0.21 (r² 0.00) | -0.36 | $1.43 |
| 2011 to 2026 | -0.42 (r² 0.94) | +0.58 (r² 0.97) | -1.15 (r² 0.86) | -0.47 | $0.65 |

## Corrections to the original analysis

1. **Minted coins were ignored.** Supply tripled over the period. Expressing transaction size
   as a share of circulating supply, the fall is about three times larger than the raw BTC
   figure shows (÷370 instead of ÷120). The whitepaper guessed the direction of this correction
   correctly; now it has a number.

2. **Change outputs.** Raw "output volume" counts the change a wallet sends back to itself.
   The analysis uses blockchain.com's estimated transaction volume, which removes it. Absolute
   levels are therefore approximate; the trends are robust to the choice.

3. **The real size of a transaction did not stay put.** This is the substantive correction.
   If transaction size tracked purchasing power, the USD value of an average transaction
   would be roughly flat. It rose 150x, from about $75 to about $11,000. Coins per transaction
   fell only about 40 % as fast as price rose (elasticity -0.42); the remaining 60 % appears as
   larger real transactions (elasticity +0.58). The fee series explains it: once fees per
   transaction went from cents to dollars in 2017, small payments were priced off chain and
   the on-chain average came to reflect exchange and large-holder transfers.

4. **The coarse model holds, but only while block space was free.** Against active addresses,
   the share of supply per transaction fell with slope -0.87 (r² 0.94) from 2011 to 2016,
   close to the model's -1. From 2017 on the relationship vanishes (slope +0.21, r² 0.00),
   because active addresses plateaued around half a million per day while the economy kept
   growing. Users stopped being a measure of the economy's size once the chain was full.
   Against market cap the slope stays around -0.5 in both eras.

5. **Mean, not median.** Free data only gives the mean, which is dominated by very large
   transfers. A median from a full node would be the right statistic and is likely to show a
   cleaner relationship.

## Update, same day: the median tells a different story

`CHAINS-COMPARISON.md` repeats this analysis with the daily **median** transaction value
(BitInfoCharts for Bitcoin, Blockchair for the other chains). The median Bitcoin transaction
was worth $63 in 2011 and $68 in 2026, with a peak yearly median of $795 in 2021, across a
23,000x price move. Elasticity of median BTC per transaction to price: -0.80 (r² 0.85). The
150x rise in the *mean* documented above is real but is the signature of exchange and whale
transfers, not of what a typical user moves. The conclusions below stand for the mean and are
softened for the median: the gauge is usable if it is the median, and it is distorted mainly
when fees price small payments off chain (2017 to 2022).

## What this means for PaSta

- **Supported:** fixed supply plus a growing economy shrinks the coin size of transactions,
  and the deflation signal the whitepaper wants to read is visible in real data, with the
  model's predicted slope, in the years the network was not capacity-constrained.
- **Not supported:** the average transaction size was not a clean purchasing-power gauge.
  Its real value moved two orders of magnitude for reasons unrelated to the coin's value.
  This is the granularity confound from `SIMULATION-RESULTS.md`, observed in the wild. A
  payments coin without a block-space cap would suffer less of it; Bitcoin cannot say how
  much less.
- **Design consequence:** whatever signal PaSta uses must be robust to changes in what an
  "average transaction" is. Supply and velocity are known on chain; spending per active user is
  the leading candidate (issue #27), and a cap on the rate of supply change is the insurance
  (issue #28).

## Figures

`docs/figures/bitcoin-price-vs-txsize.png`, `bitcoin-usd-size-and-fees.png`,
`bitcoin-share-vs-users.png`, `bitcoin-toy.png`. Regenerate with
`python -m pasta.analysis.bitcoin_report --figures docs/figures`.
