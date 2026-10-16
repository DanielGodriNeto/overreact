# overreact

Research on whether markets overreact to news and forced selling, in US stocks and crypto. Every hypothesis is
pre-registered before looking at results, tested on data it never saw, compared against a placebo, and charged
pessimistic costs. Most ideas failed, and the failures are kept.

Not a trading system: nothing here trades real money.

## Results

| Test | Result | Summary |
|---|---|---|
| Price stretch reverts (small caps) | Failed | Panic (z <= -2) hit rate 43-47%, mean ~0; small caps trend instead |
| Stretch without an 8-K reverts, with one continues | Failed | Sign flips between train and test |
| LLM reads the news ("dropped, news not bad") | Failed | Hit rate 40-44% in train and test |
| G3: buy on Binance after an Upbit listing | Failed | ~-3% per trade (n = 82); the move happens in the first second |
| G5: very negative funding -> buy spot | Failed | No predictive power |
| D1: concurrent news polling | Success | Scheduling delay p95 1.43 s -> 0.05 s |
| **G4: rebound after a liquidation cascade** | **Passed (secondary)** | Buy 1 min after, sell at +4 h: **+1.36% per trade net**, 95% CI [+0.28, +2.29], n = 293, 2024-01 to 2025-09 |

The G4 result has caveats:
- It is concentrated in a few large capitulation days. Without the 3 best days, the CI crosses zero.
- A 1-minute backtest cannot see spreads widening during a cascade.
- It is now in live paper confirmation.

Details: [LAB_crypto.md](LAB_crypto.md) (crypto) and [PLAN.md](PLAN.md) (stocks).

Method:
- Costs are 0.1% fee + 0.1% slippage per side.
- Confidence intervals come from a bootstrap by day, because cascades hit many coins at once.
- The placebo is the same coin and horizon at random times. It gives -40 bps, which is exactly the cost.
- Robustness checks cover a fixed coin list chosen in advance (no survivorship bias) and each year separately.

## Run

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python -m overreact.prices            # daily prices -> data/overreact.db
.venv/Scripts/python -m overreact.news --loop 900   # news collector, every 15 min
.venv/Scripts/python -m overreact.overnight --cost-bps 10
.venv/Scripts/python -m overreact.crypto.lab --help # crypto experiments (cascade, funding, upbit)
.venv/Scripts/python -m pytest -q                   # 54 tests
```

Edit `tickers.txt` to change the universe. Set `SEC_USER_AGENT="name email"` to enable SEC EDGAR 8-K filings.
