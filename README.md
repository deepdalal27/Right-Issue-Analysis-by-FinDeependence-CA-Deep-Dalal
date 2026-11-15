# FinDeependence — Live Rights Issue Tracker

Live tracker for **open, upcoming and recently closed rights issues** in India. Created by **CA Deep Dalal**.

**Live app:** https://deepdalal27.github.io/Right-Issue-Analysis-by-FinDeependence-CA-Deep-Dalal/

## What it shows
1. **Issue data**: record date, last cum-rights buy date, open / renunciation / close / allotment / listing dates, issue price, rights entitlement ratio, issue size, ISIN, NSE/BSE codes, RE scrip codes, registrar, Letter of Offer.
2. **Subscription status, date-wise**: the day-by-day table from Chittorgarh, plus intraday snapshots this app saves every 15 minutes.
3. **Trading volume**: last day, average per day over 5D / 1M / 3M / 1Y / all-time, average monthly and yearly volume, plus month-by-month and year-by-year tables.
4. **Highs and lows**: day, week, 1M, calendar month, 3M, 52W, calendar year and all-time, each with its date.
5. **Rights math**: discount to CMP, TERP, Rights Entitlement fair value vs market RE price, an entitlement calculator, and a calendar of every rights-issue event.

## How it works
- `scripts/scrape.py` (Python standard library only) reads Chittorgarh's rights-issue reports (#75 list, #197 live subscription) and each issue's detail page. It also pulls daily candles from Yahoo Finance (`.NS`, or `.BO` when there's no NSE symbol). It writes `data/rights.json`.
- `.github/workflows/update-data.yml` runs it every **15 min during market hours** (Mon–Fri, 09:00–17:30 IST) and every 3 hours otherwise. It then publishes `index.html` + data to the `gh-pages` branch, which serves GitHub Pages. Subscription history carries over from run to run.
- `index.html` is a single static page in the FinDeependence QIB-tracker style. It re-reads the data every 2 minutes.

Run locally: `OUT=site/data/rights.json python3 scripts/scrape.py && cp index.html logo.png site/ && python3 -m http.server -d site`

_Disclaimer: education only, not investment advice._
