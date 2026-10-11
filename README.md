# overreact

Market analysis that tries to measure human overreaction to news. Plan and findings: [PLAN.md](PLAN.md).

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python -m overreact.prices            # daily prices -> data/overreact.db
.venv/Scripts/python -m overreact.news --loop 900   # news collector, every 15 min
.venv/Scripts/python -m overreact.overnight --cost-bps 10
.venv/Scripts/python -m pytest -q
```

Edit `tickers.txt` to change the universe. Set `SEC_USER_AGENT="name email"` to enable SEC EDGAR 8-K filings.
