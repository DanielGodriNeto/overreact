# Overreact crypto: news-reaction research subsystem (plan, 2026-10-14, rev 2 after critic review)

Goal: measure, with our own receive timestamps, how fast and how far crypto prices move after news and liquidation
cascades, per source and per news type, and answer "is ~300 ms from Brazil enough?" BEFORE any trading. Personal use,
R$0, no real money, orders only on Binance spot TESTNET. Length is above one page because this is a 9-phase subsystem.

## Read this first (pushback, decided before building)
1. **Evidence comes slowly.** Listing/delisting announcements across all sources are maybe 5-20 per week. Expect 2-3 months
   for >=30 events per (source, type) bucket. Early phases gate on "the pipeline is correct", not on "there is an edge".
2. **Start the clock that cannot be backfilled first.** News receive-timestamps and liquidation events cannot be
   reconstructed later. Prices can (free dumps, see below). So order is: store -> price+liquidation recorder -> news ear -> meter.
3. **Testnet fills are not evidence of profit** (thin synthetic books, monthly wipe). Edge is judged in shadow mode on
   mainnet bid/ask data; testnet only tests the plumbing and risk caps.
4. **Likely outcome:** exchange-listing reactions are taken in well under 1 s by co-located bots. The meter may show the
   capturable part after 300 ms + costs is ~0. That is a valid, cheap answer; the plan has a STOP gate for it.
5. **Prices for the meter come mostly from dumps, not from the live recorder** (rev 2). Listing coins are rarely among a
   frozen 20-pair list, so for any event whose coin has a Binance USDT pair the path is read from data.binance.vision
   1s klines/aggTrades (free, verified). The live recorder stays for the majors (market reference), spread capture, the
   latency probe and future trading. Events whose coin has no Binance USDT pair go to a `not_measurable` bucket, counted and reported.
6. **Two latencies, never mixed (rev 2).** The reaction clock starts at the source's PUBLICATION time. Our poll delay is a
   separate "ear latency" report. With 5-60 s polling, the 300 ms question is moot until the ear is faster than the move.

## Endpoint verification (fetched 2026-10-14 from this PC's tool, not from the production task)
| Source | Result | Notes |
|---|---|---|
| Binance spot WS `wss://stream.binance.com:9443` (alt `data-stream.binance.vision`, market data only) | docs verified | 24 h max connection life, 1024 streams/conn, 5 incoming msgs/s (pings/subscribes count), `serverShutdown` event. 1s kline stream updates every 1000 ms, has event time `E`. bookTicker is real-time but has NO event time. Limits on the .vision host not confirmed identical. |
| Binance futures WS `wss://fstream.binance.com/market/...` | docs verified | New path-based routing (`/market/ws/{stream}`, `/market/stream?streams=`). `!forceOrder@arr` 1000 ms; changelog 2026-04-14 says it now sends the LARGEST liquidation per 1000 ms (older text: latest) -> cascades are undercounted, treat size as lower bound. |
| Binance OI | verified | `/fapi/v1/openInterest` weight 1 (snapshot only); `/futures/data/openInterestHist` weight 0, 5m+ periods, ~1 month history only -> must record ourselves. |
| Binance announcements | **blocked by default** | Official push topic `com_announcement_en` is on `wss://api.binance.com/sapi/wss` and REQUIRES an API key + HMAC signature (mainnet key). `/bapi/` is `Disallow` in binance.com robots.txt -> **do not use** the common unofficial bapi route. Fallback with no key: poll public `/api/v3/exchangeInfo` for new TRADING symbols (detects trading start, not the announcement). Whether exchangeInfo carries any listing timestamp: UNVERIFIED; if not, t0 for this source = first trade time of the new pair from the aggTrades dump (day+1), our poll time is only ear latency. |
| Bybit `GET api.bybit.com/v5/announcements/index?locale=en-US&type=new_crypto` | live call OK, no auth | `publishTime` ms, `dateTimestamp` author time, `url`, `type.key` (`new_crypto`, `delistings`). Rate limit page not read: UNVERIFIED. |
| OKX `GET www.okx.com/api/v5/support/announcements?annType=announcements-new-listings` | live call OK, no auth | `pTime` ms (use this), `businessPTime` = effective time (NOT publication time), `totalPage`. Official docs section and rate limit not read: UNVERIFIED. Other `annType` values: call `/api/v5/support/announcement-types`. |
| Upbit `GET api-manager.upbit.com/api/v1/announcements?os=web&page=1&per_page=5&category=trade` | live call OK | Undocumented website API: `id`, `title` (Korean), `listed_at` ISO with +09:00 **second precision** (seen `2026-10-14T16:00:41+09:00`, not ms), `category`. robots.txt has no rules; ToS NOT read. Best-effort, can vanish. |
| Coinbase | partial | `status.coinbase.com/api/v2/summary.json` valid (incidents with `created_at`). No verified listing API or RSS. Candidate: diff public `api.exchange.coinbase.com/products` (UNVERIFIED). Real listing news is mostly on X -> not covered. |
| RSS CoinDesk `/arc/outboundfeeds/rss`, Cointelegraph `/rss`, Decrypt `/feed`, The Block `/rss.xml` | all valid RSS 2.0 | RFC 822 pubDate with +0000, second precision. Robots/ToS of each NOT read: check in P0. |
| data.binance.vision | verified | spot klines include `1s`; aggTrades; `.CHECKSUM` per zip. **Spot timestamps are microseconds from 2025-01-01** (futures: ms). No liquidation/bookTicker dumps listed. Daily-file availability lag (assumed ~1 day) UNVERIFIED. |
| Binance spot testnet | partial | `testnet.binance.vision`, only `/api` (no `/sapi`), wiped about monthly without notice. Key creation flow (GitHub login?) UNVERIFIED. |
| `websockets` 17.2 on PyPI | requires >=3.11, 3.14 classifier | Only new dependency for P2 (stdlib has no WS client). Pin exactly, like the other lines in requirements.txt. |

Everything in the table is re-checked by `python -m overreact.crypto.probe` (P0) from the production machine, including
robots.txt per host, so the plan does not rest on a different network path.

## Design decisions
- New package `overreact/crypto/`, its own DB `data/crypto.db` (WAL). Reason: heavy writes must not share a lock or a
  VACUUM with the equity DB; `db.py`, `news.py`, `idle_job.py` stay untouched.
- **One time domain: exchange clock.** Local `time.time_ns()` ms + measured offset. Offset = Binance `/api/v3/time`
  midpoint, 5 samples, keep the min-RTT one, median of last 10, refreshed every 60 s, stored with RTT. Resolution is
  +/- RTT/2 (tens of ms from Brazil). Horizons below ~100 ms are not trustworthy; +1 s and up are.
- Bars are bucketed by EXCHANGE time (kline start `t`), receive times by corrected local time. Local drift cannot shift bars.
- **t0 rule (rev 2):** `events.t0_ms` = the source's publication timestamp when it is ms-precise (Bybit `publishTime`,
  OKX `pTime`). Second-precision sources (Upbit, all RSS, Coinbase status) are never used for sub-10 s capturability:
  Upbit only for scenarios L >= 10 s; RSS only for horizons >= 1 h and labelled exploratory. `recv_ms` is stored on every
  row but only feeds the ear-latency report. Source clocks can be skewed or post-dated: rows with `recv_ms - src_ts_ms < 0`
  are flagged `src_skew` and reported, not silently used.
- One generic `events` table (kind = news | liq_cluster | placebo) so meter, placebo and report work for all.
- Sources are plain functions `poll() -> list[Item]` in a dict; Telethon later is one more entry (push source calling the
  same `insert_news`). No base class.
- Prices stored as REAL (ponytail: BLOB-packed hourly arrays would be ~4x smaller; only if disk becomes a problem).

## SQLite schema (data/crypto.db)
- `symbols(id PK, venue, symbol, kind spot|perp, active)`
- `bars_1s(sym, t_s, c, h, l, qv, n, src live|dump)` PK (sym, t_s) WITHOUT ROWID. Only seconds with trades (missing =
  no trades, forward-filled by the meter with a `filled` flag). Open = previous close. Event-window bars loaded from
  dumps are inserted here (src=dump) and are pinned by the retention rule.
- `spread_5s(sym, t_s, bid, ask)` for recorded pairs, REST bookTicker snapshot every 5 s.
- `spread_day(sym, day, median_bps, p90_bps)`: one all-symbol REST bookTicker call per minute, aggregated in memory,
  ONE row per symbol per day (cheap, gives a fallback spread for any coin).
- `watch(sym, from_ms, until_ms, why)`: written by the news process when a mentioned coin has a USDT pair; the recorder
  polls it every 1 s and SUBSCRIBEs `<sym>@bookTicker` for the window (+10 min), writing `spread_evt(sym, t_ms, bid, ask,
  bq, aq)` (low rate, bounded). First sample is at most one poll interval late and is flagged `spread_src=post`.
- `bars_1m(sym, t_m, o, h, l, c, qv, n)` PK (sym, t_m), rolled up from 1s, kept forever.
- `gaps(proc, sym NULL, t_from, t_to, cause sleep|disconnect|crash, filled_by)`; `heartbeat(proc, ts_ms, info)`;
  `clock_offset(ts_ms, offset_ms, rtt_ms)`; `latency_probe(ts_ms, sym, recv_minus_E_ms)` (sampled 1/min).
- `cnews(id PK, source, ext_id, url, title, body, lang, src_cat, src_ts_ms NULL, src_ts_prec ms|s|none,
  recv_ms NOT NULL, offset_ms, hash, dup_of NULL, backlog, src_skew)` UNIQUE (source, ext_id).
- `cnews_rev(news_id, recv_ms, title, body, hash)`: edits. The original `recv_ms`/`src_ts_ms` are never changed.
- `cnews_coins(news_id, coin, method rule|llm, conf)`.
- `events(id PK, kind, ref_id, coin, t0_ms, t0_basis src_ts|first_trade|liq_peak|random, news_type, source, confounded,
  excluded NULL, price_src live|dump)`. `excluded` in {gap, sleep, backlog, not_measurable, src_skew, imprecise_ts}.
  Placebo rows: kind=placebo, ref_id = the real event.
- `reactions(event_id, h_ms, p0, r_raw, r_abn, beta, filled, pre)`; `pre`=1 rows are the -60 s/-10 s/-1 s leak check.
- `ear(news_id, ear_latency_ms)` view-style table: `recv_ms - src_ts_ms` for ms-precise sources only.
- `liq(venue, symbol, side, qty, price, avg_price, trade_ms, recv_ms)`; `funding(sym, ts_ms, rate, next_ms)`
  (from `markPrice@1s` sampled every 60 s); `oi(sym, ts_ms, oi)` every 5 min.
- Later: `examples`, `model_versions`, `rules_versions`, `trades`, `proposals` (P7-P8).

**Volume estimate (my arithmetic, MEASURE in the P2 gate):** live recorder now defaults to 3 majors + at most ~7 others
(configurable up to 30): ~0.4-0.5M rows/day x ~45 B = ~20 MB/day, ~0.6 GB per 30 days. Event windows from dumps add
~(5 min + 25 h) = ~91k rows per event-coin plus placebos (see below): 100 events x 6 placebo-inclusive windows x 91k rows
x 45 B = ~2.5 GB worst case, so dump-loaded windows are trimmed to what the horizons need (t0-5 min .. t0+25 h only for the
real event; placebo windows t0-1 min .. t0+1 h) and converted to `bars_1m` after the 24 h horizon is computed
(1s kept only for the first 10 min). Retention job (daily): delete live `bars_1s` older than 14 days EXCEPT inside any
`events` window (real or placebo, until `reactions` for it are final); `bars_1m` and `reactions` never deleted; `liq`/`news`
never deleted. Nightly `Connection.backup()` of the non-reconstructible tables (cnews*, events, reactions, liq, funding, oi,
spread_evt, trades, model_versions) to `data/backup/`, keep 7.

## 24/7 on Windows
- Three scheduled tasks, same pattern as `overreact-news` (export it with `schtasks /Query /TN overreact-news /XML`
  and copy its settings; I could not read its definition): `overreact-crypto-rec` (WS recorder, spot+futures in one
  asyncio process), `overreact-crypto-news` (poller loop), `overreact-crypto-meter` (hourly, cheap SQL plus dump
  downloads; does NOT wait for the idle job). Separate processes so a news bug never stops price capture.
- Settings: trigger at logon, restart on failure every 1 min (999 times), execution time limit OFF (default kills at 72 h),
  ignore new instance, run on battery, start only if network available. `pythonw.exe` + `RotatingFileHandler` in
  `data/crypto_*.log` (stdout is None under pythonw; same trick as `idle_job.py`). `SetThreadExecutionState` as in
  `idle_job.keep_awake` so Windows does not sleep; power plan "never sleep" when plugged in is the user's call.
- Sleep/hibernate still happens (updates, lid): on resume the recorder logs a `gaps` row (cause sleep, detected by a
  wall-clock jump vs monotonic clock or a stale heartbeat), back-fills via REST 1s klines for gaps up to 1000 s (UNVERIFIED
  that REST accepts `1s`; fallback is the dump) or leaves the gap for the dump backfill.
- Reconnect: exponential backoff with jitter (1 s .. 60 s), reset on 60 s of stable data; open the replacement
  connection at 23 h and close the old one after overlap (PK upsert dedups); handle `serverShutdown`; the library answers
  server pings; stay far below 5 msgs/s (subscribe in one message; `watch` subscriptions are batched and rate-limited to
  2 msgs/s). `python -m overreact.crypto.status` prints heartbeat age per process and gap counts; a stale heartbeat
  (>60 s) is the only alarm (printed, no email).
- Windows time: `w32tm /query /status` shows last sync. Do not change system time settings from code; the in-app offset
  makes us independent of it. Run `w32tm /resync` manually if |offset| > 500 ms (the status command warns).

## Phases (each has an executable gate; one commit per milestone)
| # | Deliverable | Files | Gate |
|---|---|---|---|
| P0 | `probe.py`: hits every endpoint once, prints status, fields, RTT, robots.txt allow/deny; adds `websockets==17.2` | `crypto/probe.py`, `requirements.txt` | Output table has no UNVERIFIED left for sources we will use; sources that fail or are disallowed are removed from `sources.py` before P3. |
| P1 | Store, clock, safe logging | `crypto/__init__.py`, `store.py`, `clock.py`, `logsafe.py`, `crypto_pairs.txt` | pytest green; offset measured 10x, stored; log redaction test passes. |
| P2 | Spot recorder (`kline_1s` x majors+few, REST bid/ask 5 s, `spread_day`, `watch`-driven bookTicker, latency probe) + futures liquidation/markPrice/OI | `recorder.py`, `derivs.py`, `retention.py`, `status.py`, `scripts/install_tasks.ps1` | 24 h unattended: >=99.5% of seconds present for BTC/ETH; 0 duplicate PKs; one forced reconnect (`--force-reconnect-after 120`) and one forced 23 h rotation (`--rotate-after 300`) with no gap; a fake `watch` row yields `spread_evt` rows; MB/day and CPU (<10% of one core) recorded in this file; liq rows > 0; a simulated sleep (SIGSTOP-style pause or test hook) writes a `gaps` row. |
| P3 | News ear (Bybit, OKX, Upbit, 4 RSS, Coinbase status, Binance exchangeInfo diff; Binance announce WS only if user approves a read-only key) | `sources.py`, `newsear.py`, `coins.py`, `coins.csv` | 48 h run: >=6 sources produce rows; 0 dup rows; per-source min poll interval respected (checked from log timestamps); edited fixture creates a `cnews_rev` and leaves `recv_ms` unchanged; `ear` report prints median/p90 `recv_ms - src_ts_ms` for Bybit/OKX; each news process downtime writes a `gaps` row. |
| P4 | Dump loader + reaction meter + placebo + report | `dumps.py`, `meter.py` | Synthetic series with injected +1% jump at known t0 gives exact `r_raw`/`r_abn` at every horizon (test); dump loader test on a fixture zip with microsecond timestamps, a bad `.CHECKSUM` is rejected; report refuses numbers when n<30 per bucket ("insufficient n"); events with a gap/sleep inside [t0-5 min, t0+h] are `excluded` and counted; `not_measurable` count shown; after 7 live days a first report exists. Optional P4b: backfill historical announcements (Bybit/OKX/Upbit pagination) against dump klines for exploratory analysis ONLY (source timestamps, no receive latency, never used for the GO gate). |
| P5 | Liquidation cascade events into the same meter | `derivs.py` (detector), `meter.py` | Detector unit test on a fixture; 7 days of data; overshoot report: max adverse excursion in 5 min and retracement fraction at +5/15/60 min vs placebo. |
| **GO/NO-GO** | Pre-registered test, see next section | this file | See "Pre-registration". |
| P6 (later) | Fast classifier: rules + TF-IDF (or small embedding) + LightGBM; LLM never in hot path | `classify.py` | p99 latency < 10 ms for 1000 items on this PC; beats rule-only baseline on a purged walk-forward set, net of costs. |
| P7 (later) | Testnet executor, shadow mode first | `binance_rest.py`, `risk.py`, `trade.py` | Fake-exchange tests prove every cap trips; 2 weeks shadow (simulated fills at mainnet bid/ask + slippage) before the first testnet order. |
| P8 (later) | Learning loop | `learn.py` | A deliberately worse candidate is rejected; rollback to previous version restores identical predictions (test). |
| P9 (any time after P3) | Telegram source via Telethon | `sources_telegram.py` | Fake-message test inserts via `insert_news` with recv_ms; no Telegram code runs unless `TELEGRAM_API_ID` exists in .env. |

## Pre-registration and GO/NO-GO (rev 2; frozen 2026-10-14, later edits must be dated and justified here)
Only these three hypotheses can open the GO gate; everything else in the reports is labelled exploratory.
- **H1** Bybit/OKX new-spot-listing announcements (ms-precise t0) for coins with a Binance USDT pair: abnormal return
  from t0+L to t0+5 min is > 0 after costs, with L = 1 s (primary) and 3 s (secondary, not gate-bearing).
- **H2** Upbit KRW listing notices (second precision, so L = 10 s only) for coins with a Binance USDT pair: abnormal
  return from t0+10 s to t0+5 min > 0 after costs.
- **H3** Liquidation cascades (long-side, on recorded perps): price return from cascade end (first 60 s without a qualifying
  liquidation) + 1 s to +15 min is > 0 after costs (overshoot-then-reversal). Cascade threshold fixed before looking:
  notional in 60 s above the 99th percentile of the previous 7 days' 60 s notionals for that symbol.
- **Statistics:** unit of resampling is the NEWS ITEM (all coins of one item move together) for H1/H2 and a 1-hour block for
  H3 (cascades cluster); cluster bootstrap, Bonferroni over 3 tests (97.5%... i.e. 98.33% two-sided CI, alpha 0.05/3).
  Data is split by time: events before the freeze date `D_freeze` (set when n>=30 for the first hypothesis, recorded here
  in a dated line) are exploration; GO requires the CI lower bound > 0 on events AFTER `D_freeze`, with the thresholds,
  L, horizons and cost model unchanged. Placebo-adjusted (real minus matched placebo) is the reported number.
- **Costs (rev 2):** 20 bps round trip (assumes Binance spot taker ~0.1% per side; current fee schedule and any BNB discount
  UNVERIFIED) PLUS the spread at t0 in bps: `spread_evt` around the event when present, else the symbol's `spread_day`
  p90 (flagged `spread_src=day`). Slippage beyond the top of book is not modelled: stated limitation.
- **Exclusions:** `excluded` events never enter the gate (gap/sleep inside the window, backlog, not_measurable, src_skew,
  imprecise_ts) and their counts are printed next to every result so selective loss is visible.
- NO-GO (any hypothesis fails or n too small after 3 months): write the negative result in PLAN.md, stop; P6-P8 not built.

## Reaction meter definition (P4)
- Event: news item x each mentioned coin that has a Binance spot USDT pair (others: `not_measurable`, still counted).
  Price path: live `bars_1s` if recorded and gap-free, else the dump 1s klines for the day(s) of the window (available
  from about day+1; the meter retries hourly). If the pair did not exist at t0 (new listing), the path starts at its first
  trade; r is measured from that first print and flagged `t0_basis=first_trade`.
- **t0 = publication time per the t0 rule** (not our receive time). p0 = last price in a bar that closed before t0 (no
  look-ahead). Horizons +1 s, 10 s, 1 m, 5 m, 1 h, 24 h (24 h only once matured). Pre-news -60 s, -10 s, -1 s to detect
  leaks (if price moves before publication, latency is moot).
- r_abn = ln return minus beta x BTC ln return; beta from trailing 24 h of 1-minute returns, clipped 0..3; BTC itself uses
  raw (and ETH-relative as a check).
- Per (source, news_type): n, median |r_abn| per horizon, `t_half` = first time the abnormal move reaches 50% of the 5-min
  move (same sign), capturable fraction = move from t0+L to t0+h over total, L in {0.3, 1, 3, 10} s, bootstrap CI.
  Capturability for L < 10 s is computed only for ms-precise t0 sources. A separate **ear-latency table** (from `ear`)
  shows which L a polling ear can actually achieve: realistic L = poll delay + order RTT, e.g. 5 s polling means mean
  2.5 s before any order, so "300 ms" is only meaningful with a push source (the Binance announcement WS or Telegram).
- Placebo (rev 2): **materialized at event creation**, not at report time. For each real event the meter inserts K=5
  `events(kind=placebo, ref_id)` rows for the same coin at a random time (seeded by the event id, reproducible), same
  hour-of-day +/-30 min on days D-1..D-7, with no news for that coin within +/-5 min and no gap. Their windows are
  pinned by the same retention rule, and their prices come from dumps like real events, so retention never deletes them.
  Report = real minus placebo.
- `confounded`=1 if another event for the same coin within +/-5 min or a BTC move >3 sigma in the window; report both ways.
- Sub-second: for the top event windows use dump aggTrades (day+1) to resolve 100 ms buckets; remember spot dump
  timestamps are microseconds.
- News type = rules first (listing, delisting, hack/exploit, regulatory, ETF, partnership, other); Korean notices use
  patterns on the title (e.g. trade-support wording) from `coins.csv` aliases. The local Ollama extractor may label in batch
  for the report only.

## Security
- **Secrets:** only in gitignored `.env` (verified `.gitignore` lists `.env`), loaded via `env.load_env`. Names:
  `BINANCE_TESTNET_API_KEY/SECRET`; trading module has no mainnet variable name and refuses any base URL other than
  the testnet constant (asserted at start and on every request). Optional `BINANCE_RO_KEY` (read-only, no trading, IP-restricted)
  only for the announcement WS: **needs your decision**. Telegram session/string = account access: `.env`/`data/` only,
  dedicated account.
- **Logging:** `logsafe.py` redacts values of env vars matching KEY/SECRET/TOKEN/SESSION and any `signature=` query;
  never log request URLs of signed calls; news text logged only truncated (200 chars) with control chars stripped. Test
  asserts a fake secret never reaches the log.
- **Untrusted news text:** SQL parameterized only; bodies stripped of HTML, capped (20 KB), responses capped (2 MB) with
  timeouts and TLS verify on; never passed to a shell or `eval`; LLM sees it only as quoted data, output parsed to a closed
  schema (as `extract.validate` already does), LLM cannot call tools, write files or touch risk caps (P8: it proposes
  from a fixed knob list, evaluated by the same gate).
- **Untrusted downloads (rev 2):** dump zips verified against their `.CHECKSUM` (sha256) before use, size-capped (e.g. 500 MB),
  read the single expected member by name with `zipfile` (never `extractall`, no path from the archive used), parsed in memory,
  host pinned to `data.binance.vision` over HTTPS, one download at a time with a polite delay.
- **Rate limiting / DoS (outbound only; no listening port, no server):** per-source minimum interval in code (start: announcement
  APIs 5 s, RSS 30-60 s, exchangeInfo 10 s, with ETag/If-Modified-Since where supported); 429/403 -> honor Retry-After, back off
  exponentially, and after 3 hits pause that source 15 min instead of retrying; a WS disconnect storm trips a circuit
  breaker (max 10 reconnects/10 min then sleep) so we never earn an IP ban. No anti-bot bypass: a challenge page = source off.
- **Auth/sessions:** none inbound. Trading: on 401/403/-2015 stop and latch, do not retry.
- **Input validation:** every WS/REST message schema-checked (types, price>0, finite), malformed dropped and counted;
  absurd jumps (>20% in 1 s) stored but flagged, not silently removed.
- **Dependencies:** `websockets` now; `lightgbm`, `scikit-learn`, `telethon` only at their phases; exact pins; `pip-audit`
  (free) before each add. No Binance SDK (HMAC via stdlib `hmac`).
- **Risk caps (P7):** constants in `risk.py` (not .env, DB or LLM-writable): symbol whitelist, max notional per position, max
  concurrent positions, max orders/min, daily loss kill switch on testnet equity; kill = file `data/KILL` plus in-memory
  latch, manual reset only; idempotent `newClientOrderId`; testnet wipe detected (equity jump) -> halt and re-baseline.

## Edge cases
- Clock drift/jump: offset per row; if |offset| changes >200 ms between samples, flag events in that minute `confounded`.
- Duplicates: UNIQUE (source, ext_id); cross-source same story = `dup_of` by normalized-title hash within 24 h, measure
  the earliest publication only. Edits: revision row, original timestamps kept (exchange posts are edited often).
- Timezones: store UTC epoch ms only; Upbit `+09:00`, RSS `+0000`; a date without tz -> `src_ts_prec = none` and it is
  ignored for t0. OKX `businessPTime` is NOT publication time. Bybit `publishTime` vs `dateTimestamp` differ: use publishTime.
- First poll of a source after downtime would "discover" old items with a fresh recv_ms: items older than the last
  successful poll are stored but flagged `backlog=1`, excluded from the ear report and from the gate.
- PC asleep / process down: a `gaps` row for the recorder or the news process makes every event whose window
  [t0-5 min, t0+h] overlaps it `excluded` (gap or sleep); events are never "repaired" silently. Dump-sourced prices do not
  need the recorder, but the ear gap (missed or late detection) still excludes the event.
- Symbols delisted/renamed, new listings: pair file re-read hourly (SUBSCRIBE/UNSUBSCRIBE, 1 message), cap 30 pairs.
- Missing seconds (no trades) vs missing data (PC asleep): distinguished with `gaps` and heartbeat.
- SQLite lock between processes: WAL, `busy_timeout` 30 s, short batched transactions (recorder flush every 5 s).
- Disk full: retention job + status warns at <10 GB free; recorder stops writing rather than corrupting.
- Python 3.14 + Windows: Proactor loop is fine for `websockets`; test on this exact interpreter.

## Tests (pytest, one file per module, no network)
`test_crypto_clock` (offset selection, min-RTT), `test_crypto_store` (upsert dedup, retention keeps real AND placebo
event windows, deletes the rest), `test_crypto_recorder` (kline message -> bar, closed-only, reconnect dedup, rotation with
fake socket, gap row on clock jump, `watch` -> spread_evt), `test_crypto_sources` (parsers on saved JSON/RSS fixtures: field
mapping, tz, ms vs s, backlog flag, t0 rule per source), `test_crypto_newsear` (dedup, revision, min-interval, 429 backoff
with fake clock), `test_crypto_coins`, `test_crypto_dumps` (checksum, zip member name, microsecond timestamps),
`test_crypto_meter` (injected jump, beta, no look-ahead, t0 = src_ts not recv, second-precision sources excluded from L<10 s,
placebo seeded and reproducible, gap exclusion, cost = 20 bps + spread), `test_crypto_stats` (cluster bootstrap by news
item, Bonferroni level), `test_crypto_derivs` (cascade detector), `test_crypto_logsafe`, later `test_risk` and `test_learn`.
Fixtures come from real responses saved by `probe` (with any secrets absent by construction).

## Rollback
Everything is additive: new package, new DB file, new tasks. Rollback = `schtasks /Delete` the three tasks, delete
`data/crypto.db` (backups in `data/backup/`), `git revert` the commits. `requirements.txt` line removable. Equity code and
`overreact.db` are never modified. Models/rules (P8) are versioned in `model_versions`/`rules_versions` with a `current`
pointer; rollback = move the pointer.

## Open decisions for you
1. Binance announcements: allow a read-only mainnet API key for the official push topic? (Default: NO, use exchangeInfo
   diff.) Note: without a push source the "300 ms" question cannot be answered, only the ear latency of polling.
2. Live pair list: 3 majors + up to ~7 others (default; the rest is read from dumps). I will propose the list at P1 from
   live volume ranks and freeze it in `crypto_pairs.txt`.
3. Is the PC allowed to stay awake 24/7? Without it expect gaps; affected events are excluded, not repaired.

Sources: https://developers.binance.com/en/docs/products/spot/web-socket-streams ,
https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/All-Market-Liquidation-Order-Streams ,
https://developers.binance.com/en/docs/products/announcements/general-info , https://github.com/binance/binance-public-data ,
https://bybit-exchange.github.io/docs/v5/announcement , https://pypi.org/project/websockets/
