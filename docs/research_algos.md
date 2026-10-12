# News-trading algos and slow-system edges (research notes, 2026-10-12)

Method: web searches returning abstracts and summaries. Full texts were NOT read. Items marked (nv) are not verified against the primary paper.

## 1. Pipeline of professional news algos
- Feeds: vendors sell machine-readable news and pre-scored analytics. Dow Jones Newswires to RavenPack metrics was about 300 ms in the (older) academic description; Dow Jones/RavenPack launched "News Analytics" in 2007 with a developer API. Sources are 2007-2011, current latency (nv).
  - https://conference.nber.org/conf_papers/f69879.pdf
  - https://www.hedgeco.net/news/?p=6605
  - https://www.cis.upenn.edu/~mkearns/newsalgotrading.pdf (Kearns et al., news algo trading; read before designing)
- EDGAR early access: Rogers, Skinner, Zechman found paid direct-feed subscribers (HFT) can receive filings up to about 1 minute before public EDGAR posting; 57% of insider purchase filings were available to at least one subscriber first; trading within 15-30 s of posting. Insider (Form 4) filings, not specifically 8-K (nv for 8-K).
  - https://www.cfo.com/accounting-2/2014/10/investors-get-jump-sec-filings-study-says/
- Ho and Zhang (TAQ ms data): leakage in the 30 min around the EDGAR acceptance timestamp; gap between acceptance and release under 2 min in market hours. Preliminary draft.
  - https://aeaweb.org/conference/2020/preliminary/paper/ysbrKYQS
- NLP, sizing and exit methods of actual funds: NOT found in public sources. Nothing verified. Practitioner claims are mostly vendor marketing.
- Implication: the first reaction (seconds to minutes) is gone by the time a 15 min poller sees it. Competing there is pointless.

## 2. Documented post-news effects
- PEAD: Martineau (Critical Finance Review): drift gone for non-micro stocks since about 2006, only recently gone for microcaps (below NYSE 20th pct). Contested: two 2025 papers claim it is alive; Subrahmanyam argues the gap is research design and microcaps are about 3% of market value. Transaction costs reportedly take 70-100% of PEAD profits (FAJ; Ng, Rusticus, Verdi 2008).
  - https://cfr.ivo-welch.info/published/papers/martineau2021rest.pdf
  - https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/
  - https://www.london.edu/faculty-and-research/academic-research/i/implications-of-transaction-costs-for-the-post-earnings-announcement-drift
- News vs no-news (Chan 2003, JFE 70): drift after bad news (underreaction), reversal after large moves with NO public news; both mainly in small, illiquid stocks. Best match to the "second wave" thesis, with the split: reversal only when there is no news.
  - https://academicnewsletter.sufe.edu.cn/info/357702
- Media tone (Tetlock 2007): pessimism pushes prices down then reverts (noise-trader reading).
  - https://papers.ssrn.com/abstract=685145
- Overnight vs intraday: Lou, Polk, Skouras (JFE 2019): reversal and momentum profits sit entirely overnight or entirely intraday with opposite signs. Akbas, Boehmer, Jiang, Koch (JFE 2022): overnight noise traders, daytime arbitrageurs who overcorrect; stronger tug of war predicts higher future returns. Glasserman et al. 2025 (WP): overnight news explains part of overnight returns.
  - https://researchonline.lse.ac.uk/id/eprint/119010
  - https://academicnewsletter.sufe.edu.cn/info/355173
  - https://arxiv.org/html/2507.04481v1
- Retail attention: Barber, Huang, Odean, Schwarz (JF 2022): top Robinhood-herded stocks have about -4.7% 20-day abnormal return (5-day about -3%); sample 2018-2020, concentrated in low-cap names and COVID period; partly continuation of a decline, not a pure reversal; short selling rises after herding (secondary).
  - https://www.smallake.kr/wp-content/uploads/2020/12/SSRN-id3715077.pdf
  - Whether it still holds post-2021: not verified.
- 8-K items: Lerman and Livnat (RAST 2010): all items cause abnormal volume and volatility, "some items" drift after filing; WHICH items: not verified. Pre-2004 rule: 4 business day deadline.
  - https://archive.nyu.edu/bitstream/2451/27579/2/SSRN-id1126816.pdf
- Offerings/dilution: shelf SEOs are shorter-gap, harder to short (Dutordoir et al. JFQA 2019); short-interest increases around announcement predict weaker long-run returns, stronger for shelf (Deshmukh et al. 2017); Henry and Koski 2010: pre-issue shorting linked to bigger discounts. No ATM-specific or small-cap drift magnitudes found.
  - https://resolve.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/abs/shelf-versus-traditional-seasoned-equity-offerings-the-impact-of-potential-short-selling/44B599740AF62025F323D17B4F2D04AC
  - https://ideas.repec.org/a/eee/corfin/v46y2017icp121-138.html

## 3. Small/illiquid and cost survival (assessment)
- The effects (Chan, PEAD, retail herding) are all strongest in small illiquid stocks, but those are the same stocks with wide spreads, borrow limits and impact. Survival after costs is the open question; no source I found shows a net-of-cost small-cap result for a retail system.
- Shorting the bad side is where the money is on paper (bad-news drift, herding reversal, dilution), and where a retail broker is weakest (borrow availability, fees, squeezes). Long-side-only or avoidance filters are the realistic paper test.

## Gaps
- No paper found with item-level 8-K drift, ATM drift, or post-2021 retail reversal.
- Lachanski and Pav 8-K item paper: not found.
- Searches were abstract-level; magnitudes quoted are from summaries.
