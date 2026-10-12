# Books and canonical references for raising PRECISION of a news-overreaction system

Date: 2026-10-12. Provenance: technique descriptions come from my prior knowledge of the books (chapter numbers from memory, NOT re-checked against the texts). Only the URLs marked [checked] were confirmed by search this session. Everything else is "not verified".

## URLs
- [checked] Lazy Prices, JF 2020 75(3):1371-1415: https://www.nber.org/papers/w25084
- [checked] Deflated Sharpe Ratio (Bailey, Lopez de Prado 2014): https://papers.ssrn.com/abstract=2460551
- [checked] Tetlock 2007, media pessimism then reversal: https://papers.ssrn.com/abstract=685145
- [checked] Chan, Jegadeesh, Lakonishok 1996 (momentum, slow reaction to earnings news): https://ideas.repec.org/a/bla/jfinan/v51y1996i5p1681-1713.html
- Not verified (from memory): Barberis-Shleifer-Vishny 1998 "A Model of Investor Sentiment" (JFE 49); Daniel-Hirshleifer-Subrahmanyam 1998 "Investor Psychology and Security Market Under- and Overreactions" (JF 53); De Bondt-Thaler 1985; Chan 2003 "Stock price reaction to news and no-news" (JB); Loughran-McDonald 2011 (JF); Bailey et al. "Probability of Backtest Overfitting" (SSRN 2326253); Jansen repo github.com/stefan-jansen/machine-learning-for-trading.

## 1. Lopez de Prado, Advances in Financial ML (AFML, 2018)
| Technique | What it is | Why it matters here | Priority | Effort |
|---|---|---|---|---|
| Purged + embargoed K-fold (Ch.7) | Drop train rows whose label window overlaps test; add a gap after test | Labels span 1-10 days and many 8-Ks cluster in time (earnings season); plain CV leaks and inflates precision | HIGH | Low (about 30 lines, or skfolio/mlfinlab-style code) |
| Sample uniqueness / average-uniqueness weights, sequential bootstrap (Ch.4) | Weight each event by 1/concurrency of overlapping labels | Overlapping 1-10d windows and same-day event clusters make samples non-IID; LightGBM overfits duplicated info | HIGH | Low (sample_weight) |
| Triple-barrier labels (Ch.3) | Label = which of profit-take, stop, or time barrier is hit first, with vol-scaled barriers | Trains on "tradeable correction" instead of raw return, which matches a 1-10d trade with a stop. Better target than residual regression alone | HIGH | Med |
| Meta-labeling (Ch.3.6) | Primary model picks the side; secondary binary model decides trade or skip (and size) | Directly trades recall for precision. Primary = overreaction residual sign, secondary = "will the correction pay after costs". Fits long-only (only the long side needs filtering) | HIGH | Med |
| Bet sizing (Ch.10) | Map predicted probability to position size, with averaging of active bets | Size by meta-label probability; avoids all-in on weak signals | MED | Low |
| Combinatorial purged CV (Ch.12) | Many train/test path combinations, giving a distribution of OOS Sharpe | Reveals whether results depend on one lucky split. Costly with 30-50k events but feasible with LightGBM | MED | Med |
| Deflated Sharpe, PBO (Ch.14, 11) | Adjust Sharpe for number of trials, skew, kurtosis; estimate probability of overfit | You will try many feature/threshold variants; essential to avoid fooling yourself. Does not raise precision, but protects against false precision | HIGH | Low |
| Feature importance (MDA/SFI, Ch.8) | Out-of-sample permutation importance, single-feature importance | Prune the noisy embedding dimensions; embeddings carry many useless dimensions | MED | Low |
| Fractional differentiation (Ch.5) | Stationary yet memory-preserving features | Marginal for event-based features | LOW | Low |
| Entropy, microstructural features (Ch.18-19) | Not suited to daily event data | LOW | - |

## 2. Lopez de Prado, ML for Asset Managers (2020)
- Denoising and detoning of covariance, NCO (Ch.2, 7): portfolio construction only. LOW now.
- Theory-guided feature importance and "False Strategy theorem" / multiple testing (Ch.8, 9 in some editions, chapter numbers not verified): reinforces DSR use. MED.
- Clustered feature importance (Ch.6): cluster the correlated embedding/features before importance, which cuts substitution effects. MED, Low-Med effort.

## 3. Ernest Chan (Quantitative Trading 2008, Algorithmic Trading 2013, Machine Trading 2017)
- Post-news drift vs reversal discussion; Chan's earnings-announcement and news-sentiment momentum material (Algorithmic Trading Ch.7 "Intraday Momentum", from memory): the point is that small, low-liquidity names tend to drift, large names revert. Use market cap / liquidity as an interaction feature. MED, Low.
- Kelly sizing with fractional Kelly and capital-based risk limits: MED, Low. Useful for the paper-trading size rule.
- Backtest hygiene (look-ahead, survivorship, data-snooping, transaction costs, short-sale constraints, split/dividend adjustment): HIGH, Low. Small-cap survivorship (delisted names) is the biggest real risk with S&P 600 historical membership, so use point-in-time constituents.
- Regime switching (Machine Trading): MED, Med. Overreaction reversal likely differs between high-VIX and low-VIX regimes; add the regime as a feature and check stability.

## 4. Grinold and Kahn, Active Portfolio Management (2nd ed. 2000)
- Information coefficient (IC) and fundamental law IR = IC * sqrt(breadth) (Ch.6): measure the signal by rank IC per event bucket, not only accuracy. With breadth of about 30-50k events over 10 years, even IC of 0.02-0.04 may be meaningful, but only if costs are lower than alpha. HIGH, Low.
- Signal "scoring" and decay (Ch.10-11 "Forecasting basics", "Advanced forecasting"): shrink forecasts as IC * vol * z-score, and estimate horizon-specific alpha decay (day 1, 3, 5, 10) to choose holding period. HIGH, Low.
- Transaction costs and turnover (Ch.16): net IC of costs is what matters for small caps (spread plus impact). HIGH, Low.

## 5. Isichenko, Quantitative Portfolio Management (2021)
- Alpha research workflow, alpha "combo" and decay/turnover/capacity trade-off (Ch.2-3 and Ch.4 from memory): treat each signal as a forecast with horizon. MED.
- Market impact and cost models (square-root law), slippage as function of ADV: use for filtering events by liquidity. HIGH for realism, Low (a filter on ADV and spread).
- Overfitting discussion (Ch.2): reinforces holdout discipline. MED.
- Neutralization of alpha against factors (size, sector, beta): residualize returns vs sector/size. MED, Low. You already use a market-adjusted baseline, so extend to sector/size/beta-adjusted.

## 6. Stefan Jansen, ML for Algorithmic Trading (2nd ed. 2020)
Code at the repo above (not verified chapter numbers; NLP is roughly Ch.14-16, text-to-signal, topic modeling, embeddings; SEC filings/earnings call example in the NLP part; Ch.7 on factor research with Alphalens; Ch.11-12 gradient boosting and long-short strategy).
- Alphalens-style factor evaluation (IC by horizon, quantile spreads, turnover): HIGH, Low; pip package alphalens-reloaded.
- Text pipelines: Loughran-McDonald finance dictionary as a cheap baseline feature set next to embeddings (word lists, not reliable for small-cap hype): MED, Low. Always compare embeddings against LM tone to see whether embeddings add anything.
- Gradient boosting practice: early stopping with time-based CV, SHAP for audit: MED, Low.
- Warning: Jansen's backtests use simplified purging, so use AFML's rather than his.

## 7. Behavioral finance: WHICH events overreact vs underreact
- Barberis-Shleifer-Vishny 1998: underreaction to single news (conservatism bias), overreaction after a streak of same-sign news. Feature: count of recent consecutive same-direction news/events per ticker; predicts that the 3rd-5th good news in a row is where reversal risk sits, while a single isolated surprise drifts. HIGH, Low.
- Daniel-Hirshleifer-Subrahmanyam 1998: overconfidence on private signals and self-attribution bias. Overreaction to private-info-like events (analyst/news hype, retail attention); continuation first, reversal later. Feature: attention proxies (news count spike, abnormal volume, retail names). MED, Low.
- Hong-Stein 1999 unified model (from memory, not verified): slow diffusion of information in low-coverage names creates momentum then reversal; use analyst coverage, institutional ownership as moderators. MED.
- Tetlock 2007 [checked]: pessimism in media followed by temporary price decline then reversal (reversal about 5 days in a course summary; not verified in the paper). Supports a long-only buy-the-overreaction-to-bad-news design; sentiment extremity is a feature. HIGH.
- Chan 2003 (not verified): stocks with news show drift, stocks with big moves but NO news show reversal. Feature: has_news flag for big price moves. HIGH for precision: separate "move with hard 8-K information" (continues) from "move without fundamental info" (reverts). Low effort.
- Chan-Jegadeesh-Lakonishok 1996 [checked]: slow reaction to earnings news, so earnings-type 8-K items (Item 2.02) should drift, not revert. Model per-item heterogeneity (Items 2.02, 1.01, 5.02, 3.02 dilution, 8.01) so the residual is evaluated per item type. HIGH, Low.
- De Bondt-Thaler 1985 (not verified): long-horizon reversal; relevant to the long-side bias.
- Kahneman (Thinking, Fast and Slow; Kahneman-Tversky prospect theory): general theory, no concrete feature. LOW.
- Practical rule that follows from this literature (my inference, not a tested result): reversals concentrate where information is soft (offerings/dilution panic, going-concern language, sentiment-driven small-cap spikes, no hard fundamentals), drift where information is hard (earnings surprise, guidance). Test as per-segment precision, not as a priori truth.

## 8. Lazy Prices (your long-horizon module) [checked]
- Findings: shorting changers and buying non-changers earned up to 188 bp/month alpha in 1995-2014 per the NBER abstract; changes in CEO/CFO language, litigation and risk factor sections matter most; no announcement effect, returns arrive later. Source above.
- Implication: your module is a long-minus-short on text similarity. For long-only retail, use only the "non-changers" leg plus avoidance filter ("exclude names whose risk factors changed heavily"); that is a weaker version. Effect decay since publication is likely (not verified for 2016-2026 small caps). Test on your own data first.

## Recommended order (highest precision gain per effort)
1. Purged/embargoed CV plus uniqueness weights (otherwise every number after is inflated).
2. Per-8-K-item and has_news segmentation (Chan 2003, CJL 1996, BSV streak feature).
3. Meta-labeling on the long side with triple-barrier targets.
4. Alphalens-style IC-by-horizon and cost-net evaluation; ADV/spread filter.
5. Deflated Sharpe over all trials logged.
6. CPCV, clustered feature importance only if time remains.

## Caveats
- None of the books proves these techniques raise precision on this specific data; they reduce leakage and selection bias (which makes reported precision honest) or add filtering. Expect lower, more honest numbers first.
- Chapter numbers are from memory.
- Paper-trading fills for illiquid small caps are optimistic; model spread and next-open fills.
