# Live-readiness research (as of 2026-10-12)

Legend: [V] verified in a fetched/search source this session; [M] from memory of stable literature, cite and re-check; [?] not verified.

## 1. Cost modeling (small caps)
- Corwin-Schultz (2012, J. Finance) high-low spread estimator; Abdi-Ranaldo (2017, RFS) close-high-low estimator. [M] Both noisy on daily data, CS goes negative often (floor at 0), biased up with overnight gaps (news events!). Use as sanity band, not as truth. Prefer real quotes: Alpaca free IEX feed gives only IEX quotes (not NBBO) [M], so spread from IEX is unreliable for tiny caps.
- Build: cost = half-spread + slippage + fees; default conservative floor for micro/small caps (e.g. 50-100 bps round trip on news days, [?] no source; calibrate from your own paper+live fills). Stress test backtest at 2x and 3x costs; edge must survive.
- Tiny orders (< ~$500-2000): impact is negligible vs spread; the real cost is spread + adverse selection on news days (wide spreads, halts). Cap order to small % of ADV dollar volume and of displayed quote size.
- Auction fills: Alpaca paper fills OPG/CLS orders at the quote like market orders, NOT at auction prices [V forum via search]. So backtest "buy at open/close" is untestable in paper; live only.
- Alpaca paper: market buys at ask, sells at bid, no price improvement, no market impact, order size not checked vs NBBO size, ~10% random partial fills, no queue position, no fees/dividends modeled [V, secondhand: forum.alpaca.markets/t/slippage-paper-trading-vs-real-trading/2801, blog.traderspost.io/article/paper-trading-vs-live-results]. Use paper to test code paths, not edge.

## 2. Evaluation honesty
- Deflated Sharpe Ratio (Bailey & Lopez de Prado 2014), PBO / CSCV (Bailey, Borwein, Lopez de Prado, Zhu 2016), Minimum Track Record Length (Bailey & LdP 2012) [M]. Log EVERY variant tried (N trials) so DSR can deflate; without trial count it is meaningless.
- Rule of thumb [M, derive with MinTRL formula]: for true annual Sharpe ~1, ~3-5+ years needed to be 95% confident SR>0; 2-3 months of paper says almost nothing about edge. Paper = engineering validation (fills logic, data gaps, kill switch), not statistical proof.
- Strategy with 1-10 day holds: trades are the sample unit; need hundreds of independent trades; events cluster in time (correlated), so effective N is smaller. Use block bootstrap by date.
- Build: pre-registered hypothesis + frozen config, walk-forward/embargo (purge overlap of 10-day holds), survivorship-bias-free universe (delisted small caps!), point-in-time news timestamps, benchmark vs IWM/random-entry, report DSR/PBO/MinTRL, treat out-of-sample paper period as one-shot holdout.

## 3. Sizing and risk
- Fractional Kelly [M]: full Kelly with estimated edge is overbetting; use 1/4 to 1/2 Kelly at most, and cap hard (e.g. 1-2% equity risk per trade, 5-10% position notional) because edge estimate error dominates.
- Vol targeting: size = risk_budget / (ATR or realized vol * stop multiple); small caps have fat tails and gap through stops, so stop = risk estimate, not guarantee.
- Max positions (e.g. 5-8), max gross exposure, per-name cap vs ADV, no averaging down.
- Kill switch: daily loss limit (e.g. 2-3% equity), weekly/drawdown limit (e.g. 10%) halts new entries, requires manual restart; heartbeat/stale-data check; reconcile broker positions vs internal state every run; idempotent client_order_id; bracket/OCO server-side stops at the broker. Numbers are design suggestions [?], not sourced.
- Halts/gaps: LULD halts on small caps, overnight news gaps; long-only avoids unbounded short loss and borrow/locate issues (shorting small caps is often unavailable or costly).

## 4. Access from Brazil
- Alpaca direct live account for Brazilian residents: NOT confirmed. Official page "countries alpaca is available" has no country list, says to contact support [V: alpaca.markets/support/countries-alpaca-is-available]. Old forum posts say Brazil blocked in the form [V, undated: forum.alpaca.markets]. Alpaca serves LatAm via partners using Broker API (e.g. Weltio) [V]. ACTION: email support asking explicitly about Brazil residency before building around it. Paper account is free and works regardless [M].
- Interactive Brokers: Brazilians commonly open via IBKR LLC (US entity) [V secondhand, investortrip.com guide]; IBKR has a mature API (TWS/IB Gateway) [M]; B3 access is not offered to Brazil residents but US stocks are fine. Confirm eligibility and fees (inactivity/minimums, market data) on IBKR site [?].
- Avenue, Nomad: no public order-entry API found [V negative search; "not verified" for absence]. Nomad = FINRA broker-dealer NIS with Global DTVM partnership [V]. Treat them as manual-only.
- PDT: SEC approved FINRA Rule 4210 amendments 2026-04-14, effective 2026-06-04, removing the PDT designation and $25k minimum; replaced by intraday margin; $2,000 margin minimum remains; brokers may phase in until 2027-10-20, so your broker's actual behavior may still be old rules [V: tradestation.com/insights/2026/05/06/day-trade-rule-change/, sofi support, quantinsti]. 1-10 day holds are mostly unaffected anyway.
- Settlement T+1 since 2024-05-28 [M]. In a cash account, using unsettled funds then selling before settlement can cause good-faith violations; with 1-10 day holds and T+1 this is manageable: track settled cash in code. Fractional shares: Alpaca supports (market/day orders, many but not all symbols; small illiquid names often not fractionable) [M, re-check asset.fractionable flag].
- Non-US persons: submit W-8BEN; US capital gains on stocks are not withheld for non-resident aliens, dividends 30% withholding (no US-Brazil income tax treaty) [M]. Estate tax exposure on US-situs assets above US$60k for non-resident aliens [M, re-check].

## 5. Brazilian tax
- Lei 14.754/2023, effective 2024: 15% flat on gains from foreign financial investments (stocks included), computed annually in the DAA (annual return), cash basis, NOT monthly DARF, no R$35k monthly exemption [V: nomadglobal.com/portal/artigos/lei-das-offshore, EY alert, juruadocs lei 14.754]. Gains converted to BRL at the PTAX of purchase and sale dates (cost basis in BRL at buy date) [M]; FX gain is therefore embedded.
- Losses: offset only against foreign financial-investment income in the SAME year; no carryforward under current law [V search summary; verify in the statute text]. Implication: a loss year gives no future tax shield; harvest/realize within year.
- MP 1.303/2025 (would have raised to 17.5% and allowed 5-year carryforward, 30-day wash-sale rule) lapsed, so not in force [V: Ato Declaratório CN 67/2025 via contabeis.com.br]. Watch for new bills.
- Foreign tax paid (dividend withholding) creditable up to the Brazilian tax [V summary]. Also Banco Central declarations (CBE) apply only above thresholds (US$100k annual / US$1M) [M, re-check].
- IOF on FX: investment remittance abroad reported at 1.10% after Decreto Legislativo 176/2025 (June 2025); 3.5% applies to other uses/cards; general 0.38% mentioned by one source [V conflicting: safra.com.br, fiemg IE_27, demarest]. Rate in Oct 2026 NOT verified; check Decreto 6.306/2007 current text. Also FX spread of the remittance provider (often larger than IOF) and wire fees; returning money repatriation IOF is 0 for inflows [M].
- Build: ledger in USD and BRL per lot (FIFO/average per RFB guidance [?]), PTAX table, annual P&L report, cost = IOF + FX spread + wire in the net-return calc. Hire/ask an accountant before the first real sale.

## Sources
- https://alpaca.markets/support/countries-alpaca-is-available
- https://forum.alpaca.markets/t/slippage-paper-trading-vs-real-trading/2801
- https://blog.traderspost.io/article/paper-trading-vs-live-results
- https://www.tradestation.com/insights/2026/05/06/day-trade-rule-change/
- https://www.quantinsti.com/articles/finra-pdt-rule-removal-2026/
- https://www.nomadglobal.com/portal/artigos/lei-das-offshore
- https://www.juruadocs.com/legislacao/art/lei_00147542023-9
- https://www.contabeis.com.br/noticias/73398/mp-do-iof-perde-validade-e-altera-regras-de-tributacao-financeira/
- https://oespecialista.safra.com.br/iof-no-cambio-remessas-exterior-2026/
- https://www.investortrip.com/articles/financial-competence/interactive-brokers-brazil-guide-local-investors
- Papers [M, not fetched]: Corwin & Schultz 2012; Abdi & Ranaldo 2017; Bailey & Lopez de Prado 2014 (DSR); Bailey et al. 2016 (PBO)
