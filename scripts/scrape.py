#!/usr/bin/env python3
"""FinDeependence Rights Issue Tracker - data builder.

Runs in GitHub Actions on a schedule and writes site/data/rights.json:
  * every rights issue listed on Chittorgarh (report 75) with dates, price, ratio, size
  * live subscription snapshot (report 197) + date-wise table from each detail page
    + our own accumulated snapshot history (kept across runs)
  * share price / volume statistics from Yahoo Finance daily candles:
      day / month / year volume averages, highs & lows (day, month, 52W, year, all-time)
  * Rights Entitlement (RE) trading candles when an RE scrip code is known

Standard library only, so the workflow needs no pip install.
"""
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import credit  # noqa: E402

CREDIT_TTL = int(os.environ.get("CREDIT_TTL_HOURS", "24")) * 3600

IST = timezone(timedelta(hours=5, minutes=30))
TODAY = datetime.now(IST).date()
OUT = os.environ.get("OUT", "site/data/rights.json")
PREV = os.environ.get("PREV", "")  # previous rights.json (for history carry-over)
DETAIL_WINDOW_DAYS = int(os.environ.get("DETAIL_WINDOW_DAYS", "120"))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
CG = "https://www.chittorgarh.com"
CG_API = "https://webnodejs.chittorgarh.com/cloud/report/data-read/{rid}/1/1/{y}/{fy}/0/all"

LOG = []


def log(*a):
    msg = " ".join(str(x) for x in a)
    LOG.append(msg)
    print(msg, flush=True)


def fetch(url, tries=3, timeout=30, accept="*/*"):
    hdr = {"User-Agent": UA, "Accept": accept, "Accept-Language": "en-IN,en;q=0.9"}
    if "chittorgarh" in url:
        hdr["Referer"] = CG + "/"
        hdr["Origin"] = CG
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=hdr)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            last = e
            if getattr(e, "code", None) == 404:
                break
            time.sleep(1.5 * (i + 1))
    log("fetch failed", url, last)
    return None


# ----------------------------------------------------------------- helpers
def clean(s):
    if s is None:
        return ""
    s = html.unescape(str(s))
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def num(s):
    if s is None or s == "":
        return None
    if isinstance(s, (int, float)):
        return float(s)
    m = re.search(r"-?\d[\d,]*\.?\d*", clean(s))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def pdate(s):
    """Parse the many date shapes Chittorgarh uses -> ISO yyyy-mm-dd or None."""
    if not s:
        return None
    s = clean(s)
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    if m:
        return m.group(1)
    s2 = re.sub(r"^[A-Za-z]{3},\s*", "", s)  # drop weekday "Tue, "
    for fmt in ("%d-%b-%Y", "%B %d, %Y", "%b %d, %Y", "%d %b %Y", "%d %B %Y", "%b %d %Y"):
        try:
            return datetime.strptime(s2, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def fy_str(d):
    y = d.year if d.month >= 4 else d.year - 1
    return f"{y}-{str((y + 1) % 100).zfill(2)}"


def cg_report(rid):
    url = CG_API.format(rid=rid, y=TODAY.year, fy=fy_str(TODAY))
    txt = fetch(url, accept="application/json")
    if not txt:
        return []
    try:
        return json.loads(txt).get("reportTableData") or []
    except json.JSONDecodeError:
        log("bad json for report", rid)
        return []


# ------------------------------------------------------- chittorgarh detail
def rsc_payload(page):
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', page, re.S)
    out = []
    for c in chunks:
        try:
            out.append(json.loads('"' + c + '"'))
        except json.JSONDecodeError:
            pass
    return "".join(out)


def enclosing_object(s, key):
    i = s.find(key)
    if i < 0:
        return None
    depth, j = 0, i
    while j > 0:
        ch = s[j]
        if ch == "}":
            depth += 1
        elif ch == "{":
            if depth == 0:
                break
            depth -= 1
        j -= 1
    depth, k, in_str, esc = 0, j, False, False
    while k < len(s):
        ch = s[k]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break
        k += 1
    try:
        return json.loads(s[j:k + 1])
    except json.JSONDecodeError:
        return None


def parse_tables(page):
    tables = []
    for tb in re.findall(r"<table.*?</table>", page, re.S):
        rows = []
        for tr in re.findall(r"<tr.*?</tr>", tb, re.S):
            cells = [clean(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
            if any(cells):
                rows.append(cells)
        if rows:
            tables.append(rows)
    return tables


def parse_sub_time(s):
    s = clean(s)
    for fmt in ("%b %d %Y %H:%M:%S", "%b %d %Y %H:%M", "%d-%b-%Y %H:%M", "%b %d %Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%dT%H:%M")
        except ValueError:
            pass
    d = pdate(s)
    return d + "T00:00" if d else s


def detail(slug, rid):
    url = f"{CG}/rights-issue/{slug}/{rid}/"
    page = fetch(url, accept="text/html")
    if not page:
        return None
    s = rsc_payload(page)
    o = enclosing_object(s, '"bse_scripcode"') or {}
    d = {
        "url": url,
        "isin": o.get("isin") or None,
        "nse": (o.get("nse_symbol") or "").strip() or None,
        "bse": str(o.get("bse_scripcode") or "").strip() or None,
        "reNse": (o.get("re_nse_symbol") or "").strip() or None,
        "reBse": str(o.get("re_bse_scripcode") or "").strip() or None,
        "faceValue": clean(o.get("face_value")) or None,
        "issuePriceTxt": clean(o.get("issue_price")) or None,
        "issueShares": num(o.get("issue_size_in_shares_number") or o.get("issue_size_in_shares")),
        "issueAmtTxt": clean(o.get("issue_size_in_amt")) or None,
        "entitlement": clean(o.get("entitlement")) or None,
        "entRights": num(o.get("entitlement_rights_equity_share")),
        "entHeld": num(o.get("entitlement_fully_paid_equity_share")),
        "listingAt": clean(o.get("listing_at")) or None,
        "terms": clean(o.get("terms_of_payment")) or None,
        "lotSize": clean(o.get("market_lot_size")) or None,
        "minQty": clean(o.get("minimum_order_quantity")) or None,
        "leadManagers": clean(o.get("lead_managers")) or None,
        "registrar": clean(o.get("registrar_name_1")) or None,
        "registrarSite": o.get("reg_website_1") or None,
        "registrarEmail": o.get("registrar_1_email") or None,
        "letterOfOffer": o.get("letter_of_offer_url") or None,
        "allotmentUrl": o.get("allotment_url") or None,
        "website": o.get("website") or None,
        "logo": ("https://www.chittorgarh.net/images/ipo/" + o["logo_url"]) if o.get("logo_url") else None,
        "dates": {
            "lastBuy": pdate(o.get("last_day_to_buy_shares_dt")),
            "record": pdate(o.get("record_dt")),
            "reCredit": pdate(o.get("rights_entitlements_credit_dt")),
            "open": pdate(o.get("issue_open_date")),
            "renunciation": pdate(o.get("timetable_renunciation_dt")),
            "close": pdate(o.get("issue_close_date")),
            "allotment": pdate(o.get("timetable_allotment_dt")),
            "credit": pdate(o.get("timetable_credit_dt")),
            "listing": pdate(o.get("timetable_listing_dt") or o.get("listing_dt")),
        },
        "subsTable": None,
        "objects": [],
    }
    for t in parse_tables(page):
        head = [h.lower() for h in t[0]]
        if head and head[0] == "date" and any("subscription" in h for h in head):
            rows = []
            for r in t[1:]:
                if len(r) < 2:
                    continue
                row = {"at": parse_sub_time(r[0])}
                for h, v in zip(t[0][1:], r[1:]):
                    hl = h.lower()
                    if "subscription" in hl:
                        row["times"] = num(v)
                    elif "bid" in hl:
                        row.setdefault("bids", {})[h.replace(" Bid Quantity", "").strip() or "Total"] = num(v)
                rows.append(row)
            d["subsTable"] = rows
        elif len(head) >= 3 and "issue objects" in head[1]:
            for r in t[1:]:
                if len(r) >= 3 and r[1] and r[1].lower() != "total":
                    d["objects"].append({"obj": r[1], "amt": num(r[2])})
    return d


# ------------------------------------------------------------- yahoo prices
def yahoo(symbol, rng="max"):
    """Daily candles. range=max makes Yahoo downsample to weekly/monthly, so full
    history is requested with period1/period2, which keeps 1d granularity."""
    q = urllib.parse.quote(symbol)
    if rng == "max":
        span = f"period1=0&period2={int(time.time()) + 86400}"
    else:
        span = f"range={rng}"
    for host in ("query1", "query2"):
        txt = fetch(f"https://{host}.finance.yahoo.com/v8/finance/chart/{q}?{span}&interval=1d"
                    "&includePrePost=false&events=div%2Csplit", tries=2)
        if not txt:
            continue
        try:
            res = json.loads(txt)["chart"]["result"][0]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            continue
        ts = res.get("timestamp") or []
        qd = (res.get("indicators", {}).get("quote") or [{}])[0]
        candles = []
        for i, t in enumerate(ts):
            o, h, l, c, v = (qd.get(k, [None] * len(ts))[i] for k in ("open", "high", "low", "close", "volume"))
            if c is None or h is None or l is None:
                continue
            dt = datetime.fromtimestamp(t, IST).date().isoformat()
            candles.append([dt, r2(o), r2(h), r2(l), r2(c), int(v or 0)])
        # Yahoo sometimes repeats the live day; keep last per date
        dedup = {}
        for cnd in candles:
            dedup[cnd[0]] = cnd
        candles = [dedup[k] for k in sorted(dedup)]
        if candles:
            return {"symbol": symbol, "meta": res.get("meta", {}), "candles": candles}
    return None


def r2(x):
    return None if x is None else round(float(x), 2)


def avg(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs)) if xs else None


def hl_of(cs):
    if not cs:
        return None
    hi = max(cs, key=lambda c: c[2])
    lo = min(cs, key=lambda c: c[3])
    return {"high": hi[2], "highOn": hi[0], "low": lo[3], "lowOn": lo[0]}


def price_stats(y):
    cs = y["candles"]
    last = cs[-1]
    ld = date.fromisoformat(last[0])
    meta = y.get("meta", {})

    def since(days):
        cut = (ld - timedelta(days=days)).isoformat()
        return [c for c in cs if c[0] > cut]

    # month & year aggregates
    months, years = {}, {}
    for c in cs:
        for bucket, key in ((months, c[0][:7]), (years, c[0][:4])):
            b = bucket.setdefault(key, {"o": c[1], "h": c[2], "l": c[3], "c": c[4], "v": 0, "n": 0,
                                        "hOn": c[0], "lOn": c[0]})
            if c[2] > b["h"]:
                b["h"], b["hOn"] = c[2], c[0]
            if c[3] < b["l"]:
                b["l"], b["lOn"] = c[3], c[0]
            b["c"] = c[4]
            b["v"] += c[5]
            b["n"] += 1
    mkeys = sorted(months)
    ykeys = sorted(years)
    full_months = [months[k] for k in mkeys[:-1]][-12:]  # completed months only
    full_years = [years[k] for k in ykeys[:-1]]
    vols = [c[5] for c in cs]
    prev_close = cs[-2][4] if len(cs) > 1 else None
    stats = {
        "symbol": y["symbol"],
        "exchange": meta.get("fullExchangeName") or meta.get("exchangeName"),
        "asOf": last[0],
        "ltp": meta.get("regularMarketPrice") or last[4],
        "prevClose": prev_close,
        "chgPct": round((last[4] - prev_close) / prev_close * 100, 2) if prev_close else None,
        "firstTrade": cs[0][0],
        "volume": {
            "lastDay": last[5],
            "avg5D": avg(v[5] for v in cs[-5:]),
            "avg1M": avg(v[5] for v in since(30)),
            "avg3M": avg(v[5] for v in since(91)),
            "avg1Y": avg(v[5] for v in since(365)),
            "avgAll": avg(vols),
            "avgMonthly12M": avg(m["v"] for m in full_months),
            "avgYearly": avg(yy["v"] for yy in full_years),
            "thisMonth": months[mkeys[-1]]["v"],
            "thisYear": years[ykeys[-1]]["v"],
            "maxDay": max(cs, key=lambda c: c[5])[5],
            "maxDayOn": max(cs, key=lambda c: c[5])[0],
        },
        "hl": {
            "day": {"high": last[2], "low": last[3], "open": last[1], "close": last[4], "on": last[0]},
            "week": hl_of(since(7)),
            "month": hl_of(since(30)),
            "calMonth": hl_of([c for c in cs if c[0][:7] == mkeys[-1]]),
            "m3": hl_of(since(91)),
            "w52": hl_of(since(365)),
            "calYear": hl_of([c for c in cs if c[0][:4] == ykeys[-1]]),
            "all": hl_of(cs),
        },
        "monthly": [{"m": k, **{kk: months[k][kk] for kk in ("o", "h", "l", "c", "v", "n", "hOn", "lOn")},
                     "avgV": round(months[k]["v"] / months[k]["n"])} for k in mkeys[-24:]],
        "yearly": [{"y": k, **{kk: years[k][kk] for kk in ("o", "h", "l", "c", "v", "n", "hOn", "lOn")},
                    "avgV": round(years[k]["v"] / years[k]["n"])} for k in ykeys],
        "daily": [c for c in cs[-260:]],
    }
    return stats


def yahoo_search(term):
    """Resolve an ISIN / scrip code to Yahoo tickers on NSE/BSE."""
    txt = fetch("https://query2.finance.yahoo.com/v1/finance/search?q=" + urllib.parse.quote(term)
                + "&quotesCount=6&newsCount=0", tries=2)
    try:
        quotes = json.loads(txt or "{}").get("quotes") or []
    except json.JSONDecodeError:
        return []
    syms = [q.get("symbol") for q in quotes if str(q.get("symbol", "")).endswith((".NS", ".BO"))]
    return sorted(syms, key=lambda s: not s.endswith(".NS"))


def pick_symbol(d):
    cands = []
    if d.get("nse"):
        cands.append(d["nse"] + ".NS")
    if d.get("bse"):
        cands.append(d["bse"] + ".BO")
    return cands


def is_daily(cs):
    if len(cs) < 6:
        return True
    gaps = sorted((date.fromisoformat(b[0]) - date.fromisoformat(a[0])).days for a, b in zip(cs[-40:], cs[-39:]))
    return gaps[len(gaps) // 2] <= 3


def stock_history(det):
    tried = []
    cands = pick_symbol(det)
    for i in range(2):
        for sym in cands:
            if sym in tried:
                continue
            tried.append(sym)
            y = yahoo(sym)
            time.sleep(0.3)
            if y and len(y["candles"]) >= 2:
                if not is_daily(y["candles"]):  # safety net: fall back to 10y daily
                    y2 = yahoo(sym, rng="10y")
                    if y2 and is_daily(y2["candles"]):
                        y = y2
                return y
        if i == 0:  # nothing worked -> ask Yahoo search by ISIN / scrip code
            cands = []
            for term in (det.get("isin"), det.get("bse"), det.get("nse")):
                if term:
                    cands += [s for s in yahoo_search(term) if s not in cands]
                    if cands:
                        break
            log("  yahoo search", det.get("isin"), "->", cands or "none")
    return None


# -------------------------------------------------------------------- build
def status_of(op, cl, today):
    t = today.isoformat()
    if op and cl:
        if t < op:
            return "upcoming"
        if t <= cl:
            return "open"
        return "closed"
    if op and t < op:
        return "upcoming"
    if cl and t > cl:
        return "closed"
    return "upcoming"


def main():
    prev = {}
    if PREV and os.path.exists(PREV):
        try:
            prev = {str(i["id"]): i for i in json.load(open(PREV)).get("issues", [])}
            log("loaded previous issues:", len(prev))
        except Exception as e:  # noqa: BLE001
            log("could not read previous data", e)

    rows = cg_report(75)
    log("report 75 rows:", len(rows))
    if not rows:
        if prev:
            log("source down - keeping previous data")
            sys.exit(0)
        sys.exit("no data from chittorgarh")
    subs = {str(r.get("~id")): r for r in cg_report(197)}
    log("report 197 rows:", len(subs))

    issues = []
    cutoff = (TODAY - timedelta(days=DETAIL_WINDOW_DAYS)).isoformat()
    for r in rows:
        rid = str(r.get("~id"))
        slug = r.get("~URLRewrite_Folder_Name")
        p = prev.get(rid, {})
        it = {
            "id": int(rid),
            "slug": slug,
            "name": clean(r.get("Company Name")),
            "title": clean(r.get("~compare_name")) or clean(r.get("Company Name")),
            "logo": r.get("~compare_image") or None,
            "cgUrl": f"{CG}/rights-issue/{slug}/{rid}/",
            "record": pdate(r.get("~Record_dt") or r.get("Record Date")),
            "open": pdate(r.get("~Issue_Open_Date") or r.get("Issue Open")),
            "renunciation": pdate(r.get("~Timetable_Renunciation_dt") or r.get("Renunciation of Rights Entitlements")),
            "close": pdate(r.get("~Issue_Close_Date") or r.get("Issue Close")),
            "price": num(r.get("Issue price (Rs. Per Share)")),
            "sizeCr": num(r.get("Issue Size (Rs Cr)")),
            "ratio": clean(r.get("Rights Issue Ratio")) or None,
            "cmp": num(r.get("CMP of Share")),
            "reCmp": num(r.get("CMP of Rights Entitlement")),
        }
        it["status"] = status_of(it["open"], it["close"], TODAY)

        # ---- subscription snapshot + history (accumulated by us)
        hist = list(p.get("subsHistory") or [])
        s = subs.get(rid)
        if s:
            snap = {"at": (s.get("~Bid_dt") or "")[:16] or parse_sub_time(s.get("Subscription as on")),
                    "times": num(s.get("Subscription (x)")),
                    "bidQty": num(s.get("Total Bid Quantity")),
                    "shares": num(s.get("Issue Size (Shares)"))}
            it["subscription"] = snap
            if snap["at"] and not any(h.get("at") == snap["at"] for h in hist):
                hist.append(snap)
        elif p.get("subscription"):
            it["subscription"] = p["subscription"]
        hist.sort(key=lambda h: h.get("at") or "")
        it["subsHistory"] = hist[-200:]

        recent = (it["close"] or "9999") >= cutoff or it["status"] != "closed"
        # ---- detail page (recent / active only; older ones keep cached detail)
        det = None
        if recent and slug:
            det = detail(slug, rid)
            time.sleep(0.4)
        if det is None:
            det = p.get("detail")
        it["detail"] = det
        if det:
            dd = det.get("dates") or {}
            for k in ("record", "open", "close", "renunciation"):
                if not it.get(k) and dd.get(k):
                    it[k] = dd[k]
            it["status"] = status_of(it["open"], it["close"], TODAY)
            # merge detail page date-wise subscription into history
            for row in det.get("subsTable") or []:
                if row.get("at") and not any(h.get("at") == row["at"] for h in it["subsHistory"]):
                    bq = sum(v for v in (row.get("bids") or {}).values() if v)
                    it["subsHistory"].append({"at": row["at"], "times": row.get("times"),
                                              "bidQty": bq or None, "src": "cg"})
            it["subsHistory"].sort(key=lambda h: h.get("at") or "")

        # ---- price & volume (recent / active only)
        stats, re_stats = None, None
        if recent and det:
            y = stock_history(det)
            if y:
                stats = price_stats(y)
            re_syms = []
            if det.get("reNse"):
                re_syms.append(det["reNse"] + ".NS")
            if det.get("reBse"):
                re_syms.append(det["reBse"] + ".BO")
            for sym in re_syms:
                y = yahoo(sym, rng="3mo")
                time.sleep(0.3)
                if y and y["candles"]:
                    cs = y["candles"]
                    re_stats = {"symbol": sym, "ltp": y["meta"].get("regularMarketPrice") or cs[-1][4],
                                "asOf": cs[-1][0], "hl": hl_of(cs), "totalVol": sum(c[5] for c in cs),
                                "avgVol": avg(c[5] for c in cs), "daily": cs}
                    break
        it["stock"] = stats or (None if recent else p.get("stock"))
        it["re"] = re_stats or p.get("re")
        if stats and not it["cmp"]:
            it["cmp"] = stats["ltp"]
        if re_stats and not it["reCmp"]:
            it["reCmp"] = re_stats["ltp"]
        # ---- credit rating & default history (cached for CREDIT_TTL per company)
        pc = p.get("credit")
        fresh = pc and time.time() - (pc.get("fetchedAt") or 0) < CREDIT_TTL
        if recent and det and not fresh and (det.get("nse") or det.get("bse")):
            try:
                pc = credit.credit_profile(nse=det.get("nse"), bse=det.get("bse"), isin=det.get("isin"), log=log) or pc
            except Exception as e:  # noqa: BLE001 - never let one company break the run
                log("  credit failed", it["name"], e)
        it["credit"] = pc
        issues.append(it)
        if recent:
            log(f"{it['status']:8} {it['name'][:40]:40} detail={'y' if det else 'n'} "
                f"stock={stats['symbol'] if stats else '-'} re={re_stats['symbol'] if re_stats else '-'}")

    order = {"open": 0, "upcoming": 1, "closed": 2}
    issues.sort(key=lambda i: (order[i["status"]], i["close"] or "9999") if i["status"] != "closed"
                else (2, "".join(chr(255 - ord(ch)) for ch in (i["close"] or ""))))
    out = {
        "generatedAt": datetime.now(IST).isoformat(timespec="seconds"),
        "source": "chittorgarh.com (rights issue reports 75 & 197, detail pages) + Yahoo Finance daily candles",
        "counts": {k: sum(1 for i in issues if i["status"] == k) for k in order},
        "issues": issues,
    }
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    log("wrote", OUT, out["counts"], f"{os.path.getsize(OUT)/1024:.0f} KB")


if __name__ == "__main__":
    main()
