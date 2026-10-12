# Free tools for overreact (checked 2026-10-12)

Legend: V = verified on a primary/official page; T = third-party only; N = not verified.

## 1. News and filings
- EDGAR APIs (V): data.sec.gov submissions JSON updates "typically under one second"; XBRL under a minute; no streaming/websocket; nightly bulk ZIP ~3am ET. Free. https://www.sec.gov/search-filings/edgar-application-programming-interfaces
  - Latest-filings Atom/RSS exists (V, https://www.sec.gov/developer). Its refresh interval: N.
  - Rate limit 10 req/s per user, descriptive User-Agent required (T: edgartools/R docs; N on sec.gov page). Keep <=9/s.
  - Recommendation: ADOPT. Poll the submissions endpoint for a watchlist of CIKs (or the latest-filings feed) every 1-2 min instead of 15 min. Small effort.
- Alpaca news (Benzinga) (V): REST history since 2015, websocket real-time news exists. Free-plan access and limits: N (docs silent). https://docs.alpaca.markets/docs/historical-news-data
  - Recommendation: TRY. Test with a free paper-account key. Also gives a Benzinga history for backtests (check how far back the key returns).
- Alpaca market data (T/V): free Basic = IEX only; REST 200 calls/min (docs). Websocket 1 connection and 30 symbols for trades/quotes is from a DEPRECATED page (N for now). https://docs.alpaca.markets/docs/market-data
- Finnhub (T): free ~60 calls/min, company-news endpoint, personal use only. Daily cap unclear. ADOPT as a second news source (try). https://finnhub.io
- Polygon is now Massive (T): free = 5 calls/min, EOD freshness, 2 years of history; real-time is paid. SKIP except for 2-year minute bars. https://massive.com/pricing (N: not fetched)
- FMP (T): free 250 req/day, 500 MB/30d bandwidth, non-commercial; delisted-companies list is free. TRY for the delisted list only.
- GDELT DOC 2.0 (T): no key, ~1 req/5 s, only the last ~3 months, tone timeline via gdeltdoc. Official docs not read (N). For older dates use the GDELT raw files (N). Recommendation: SKIP for small caps (coverage is mostly large-cap and global; noisy tone).

## 2. Prices
- yfinance daily is fine for adjusted daily bars, but it is unofficial scraping and breaks without notice (known behaviour). Cache everything in SQLite, never re-fetch.
- Alpaca IEX bars: roughly 2-3% of consolidated volume (general knowledge, N). Fine for timing a signal, wrong for volume-based features on illiquid small caps. SIP is paid ($99/mo, T).
- Survivorship: no good free price source for delisted tickers was found. Free workable pattern: build the universe from the FMP delisted list or EDGAR (T), and from today forward snapshot your own universe daily (cheap and reliable). marketparquet has a free sample only; the full set is $79 (T). Norgate has a 21-day trial (T). Recommendation: ADOPT the daily self-snapshot; accept the bias for history and say so in results.

## 3. Backtest frameworks
- backtesting.py (V): 0.6.6 released 2026-07-22, Python >=3.9. Single-asset, event loop. https://pypi.org/project/backtesting/
- vectorbt OSS (V partial): repo active (copyright 2026), PRO is the paid upsell; 3.14 support only T (stork.ai), N.
- Nautilus Trader (T): supports Python 3.12-3.14, 1.231.0 (Aug 2026) is the last v1; v2 Rust core is in RC. Heavy. SKIP.
- zipline-reloaded (T): 2.4; 3.14 not stated; heavy bundle ingestion. SKIP.
- Qlib: 2026 activity N. SKIP (China-market oriented, daily factor model workflow).
- Recommendation for event-driven daily research: ADOPT a ~50-line pandas event study (entry at t+1 open, fixed hold N days, costs/slippage on illiquid names) feeding LightGBM. A framework adds little here. Use backtesting.py only if you want trade stats quickly.

## 4. Speed
- pandas+SQLite at your data size is not the bottleneck (T: for small data the difference is negligible). Real wins: WAL mode, indexes on (ticker, ts), batch inserts, async/concurrent HTTP with per-host rate limits, and caching. DuckDB can read the SQLite file directly for analytics: TRY later. Polars: SKIP now.
- Embeddings in Ollama: no RX 7600 benchmark exists (T search found none, N). Ollama Windows needs a ROCm v7 driver or Vulkan; Vulkan is experimental via OLLAMA_VULKAN=1 (T). Size fit on 8 GB: nomic-embed-text, embeddinggemma (300M), qwen3-embedding:0.6b (639 MB), bge-m3 (568M) all fit. Measure with your own 200 headlines and `ollama ps`. Relative throughput on a 3060 (T): nomic 5800 tok/s > bge-m3 2400. TRY nomic or embeddinggemma first.
- ONNX/DirectML: not researched (N).

## 5. NLP
- FinBERT (ProsusAI/finbert) is the established sentiment baseline (T: HF/papers). ~110M params, runs on CPU in ms per headline, far cheaper than qwen3:1.7b. ADOPT as the fast first-pass tag. No 2026 head-to-head of financial sentiment models found (N). FinGPT: not found (N), SKIP.
- FinMTEB (V paper arXiv 2502.10990): benchmark of embeddings on finance; Fin-E5 tops it but is 7B (does not fit). Finding: BoW beats dense embeddings on financial STS, so TF-IDF for dedup/novelty is a legit baseline. https://arxiv.org/abs/2502.10990
- FinModernBERT-embed claims (self-reported, N).

## Key risks
- Free tiers change; many limits are from comparison sites (T).
- Free real-time price data is IEX only, so intraday small-cap volume is understated.
- Survivorship bias cannot be fixed for past data for free.
