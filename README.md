# FinDeependence — Live Rights Issue Tracker

Live tracker for **open, upcoming and recently closed rights issues** in India. Created by **CA Deep Dalal**.

**Live app:** https://deepdalal27.github.io/Right-Issue-Analysis-by-FinDeependence-CA-Deep-Dalal/

## What it shows
1. **Issue data**: record date, last cum-rights buy date, open / renunciation / close / allotment / listing dates, issue price, rights entitlement ratio, issue size, ISIN, NSE/BSE codes, RE scrip codes, registrar, Letter of Offer.
2. **Subscription status, date-wise**: the day-by-day table from Chittorgarh, plus intraday snapshots this app saves every 15 minutes.
3. **Trading volume**: last day, average per day over 5D / 1M / 3M / 1Y / all-time, average monthly and yearly volume, plus month-by-month and year-by-year tables.
4. **Highs and lows**: day, week, 1M, calendar month, 3M, 52W, calendar year and all-time, each with its date.
5. **⭐ RE Ratings (new)**: every open or upcoming issue gets a 0–100 score and a 5-star rating, plus a plain action with ₹ numbers:
   - *If you hold the shares*: Apply / Sell your REs / Apply cautiously / Prefer selling.
   - *If you don't*: Buy RE & apply / RE cheap but risky / Marginal / Don't buy RE, with a **max sensible RE buy price**.
   - Score factors: safety cushion vs the stock's volatility up to listing (30), credit rating & default history (20), discount (15), subscription demand (12), price trend (10), liquidity (8), dilution (5).
   - Also shows the chance of trading below the issue price at listing, RE fair value vs market, a worked ₹ example for a sample holding, and a beginner's guide to rights issues.
6. **Credit rating & default check (new)**: for each company, the latest credit rating (agency, grade, outlook, Issuer-Not-Cooperating flag) is read from the agencies' own rationale documents listed on Screener.in. A **default record** is flagged when a `D` grade appears now or in the agency's 3-year rating history, or when the rationale reports delays in debt servicing, NPA/SMA, a one-time settlement/restructuring, or insolvency/NCLT/CIRP. Every flag links to its source. Net worth, borrowings, debt/equity, interest cover, promoter pledge and Screener's red-flag checklist are shown too.
   - Credit is a 20-point factor in the score. A company rated **D now is capped at 30**; one with a default, insolvency or settlement in recent history is capped at **50**; reported debt-servicing delays cap it at 55.
   - Credit data is cached for 24 h per company (`CREDIT_TTL_HOURS`).
7. **Rights math**: discount to CMP, TERP, Rights Entitlement fair value vs market RE price, an entitlement calculator, and a calendar of every rights-issue event.

## How it works
- `scripts/scrape.py` (Python standard library only) reads Chittorgarh's rights-issue reports (#75 list, #197 live subscription) and each issue's detail page. It also pulls daily candles from Yahoo Finance (`.NS`, or `.BO` when there's no NSE symbol). It writes `data/rights.json`.
- `.github/workflows/update-data.yml` runs it every **15 min during market hours** (Mon–Fri, 09:00–17:30 IST) and every 3 hours otherwise. It then publishes `index.html` + data to the `gh-pages` branch, which serves GitHub Pages. Subscription history carries over from run to run.
- `index.html` is a single static page in the FinDeependence QIB-tracker style. It re-reads the data every 2 minutes.

Run locally: `OUT=site/data/rights.json python3 scripts/scrape.py && cp index.html logo.png site/ && python3 -m http.server -d site`

_Disclaimer: education only, not investment advice._
