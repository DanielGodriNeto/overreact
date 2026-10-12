# Overreact: plan

Thesis: humans overreact to news. Two charts per asset: **predicted price** (probability cone)
and **theoretical price** (fair-value band). The gap between real and theoretical is the signal.
Personal use, paper trading first, cost R$0 (local models, free data).

## Decisions
- Market: US small/mid caps (has open/close for the overnight test, free paper trading via Alpaca, many niche names).
- Horizon: days to weeks.
- Data: yfinance (prices), RSS: PR Newswire, Reddit, Yahoo per-ticker, SEC EDGAR 8-K. No X scraping (ToS, login, breaks weekly).
- Storage: SQLite (`data/overreact.db`, not versioned).
- Hardware: RX 7600 (8 GB) + 32 GB RAM -> small local LLM (3-8B quantized via Ollama/llama.cpp Vulkan), LightGBM on CPU.
- The LLM never decides. It turns text into numbers; a quant model decides; fixed rules cap risk.

## Decision pipeline
1. Filter (Laya, fine-tuned): relevant or not. 2. Extract (local LLM -> JSON: ticker, sector, direction, intensity, confidence).
3. Features per ticker/day: sentiment, news-volume spike, deviation from fair band, momentum, volume, gap.
4. Decide (LightGBM): P(return over N days > costs). 5. Risk: position cap, stop, daily loss cap, kill switch.
Labels for fine-tuning come for free: what the price did 1-3 days after each news item.

## Phases
| # | Deliverable | Gate |
|---|---|---|
| 1 | Prices + 24/7 news collector + overnight backtest | Data flowing daily (DONE; collector = Windows task `overreact-news`, log in data/collector.log) |
| 2 | Fair-value band + "big deviation reverts?" backtest | DONE: price-only reversion fails on small caps (see findings) |
| 3 | Local LLM extractor + auto-labels + Laya fine-tune | Beats chance on unseen news |
| 4 | LightGBM decider + TimesFM 2.5 cone (Lag-Llama as fallback) + Alpaca paper trading + prediction journal | 3+ months beating IWM after costs |
| 5 | Polished UI (Next.js + TradingView Lightweight Charts) | Can move earlier |
| 6 | Small real money, hard limits | Only if phase 4 passes |

## Phase 1 findings (2026-10-11, data since 2016)
- Overnight (buy close, sell open) beats holding gross on every volatile small cap; intraday loses almost everything.
- Break-even cost is only ~4-28 bps per side. At 10 bps most volatile names still profit; at 25 bps almost all lose.
- Caveats before trusting it: survivorship bias (tickers picked today), yfinance "open" may be the first print rather
  than the official opening auction, spreads on small caps at open are wide. Next: measure real fills with Alpaca paper
  market-on-close / market-on-open orders.

## Phase 2 findings (2026-10-12, `python -m overreact.fairvalue`)
- Fair band = rolling mean of log price +/- 2 std; z = stretch. Train <2022, test >=2022, demeaned forward returns.
- Small caps: NO reliable reversion. Panic (z<=-2) -> hit rate 43-47%, mean ~0. Euphoria (z>=2) -> ~55% small pullbacks
  but rare huge continuations make the mean negative for a reversal trade: price-only, small caps trend (momentum).
- SPY/IWM: weak reversion after panic (window 60, z<=-2.5: 64-68% hit at 5-10d, +0.3-0.5% net), few samples (113).
- Only 2 parameter sets tried on purpose (more = data mining). Overlapping windows inflate n.
- Conclusion: a stretched price alone does not say "overreaction". Key hypothesis for phase 3:
  **stretch WITHOUT hard news reverts, stretch WITH hard news (8-K, earnings) continues.** News tells them apart.

## Phase 3 progress (2026-10-12)
- `edgar.py`: 10 years of SEC hard filings (8-K, 10-Q/K, 424B offerings) for the universe, point-in-time.
- Test "stretch WITHOUT filing reverts, WITH filing continues": NOT supported. Panic without filing still ~46% hit;
  euphoria with filing flips sign between train (-6% at 5d) and test (+1.9%) = noise. Knowing a filing exists is not
  enough; WHAT it says matters -> LLM over filing/news text.
- `extract.py`: local LLM (qwen3:1.7b via Ollama, 7/8 on a tiny labeled set vs 5/8 for qwen3:4b, ~5 s/item on RX 7600)
  -> ticker, direction, confidence, category; output validated and clamped, unknown tickers dropped.
- Idle batch (Windows task `overreact-idle`, log data/idle_job.log): starts after 10 min idle, keeps PC awake,
  stops when user returns, resumes next idle. Fetches ~1,600 8-K texts (+EX-99 press releases) and runs the LLM.
- Next, once the batch finishes: test
  "panic + LLM says neutral/positive news -> reverts" on 10 years; auto-labels for Laya fine-tune.

## Security checklist
- No API keys in code; future Alpaca keys go in `.env` (gitignored), paper keys only until phase 6.
- SEC_USER_AGENT from env, never hardcoded.
- Real-money phase: hard caps enforced in code, not in config the model can change.

## TimesFM (checked 2026-10-12)
- Use it for the **probability cone** (quantiles) and for forecasting volatility/volume, not for buy/sell direction.
- Studies: zero-shot TimesFM/Chronos on daily returns ~ random walk (negative out-of-sample R², ~50% direction);
  LightGBM/CatBoost beat them. So the decider stays LightGBM.
- 2.5 is 200M params -> runs on CPU. Gate: its cone must be better calibrated (interval coverage) than a naive volatility cone.
