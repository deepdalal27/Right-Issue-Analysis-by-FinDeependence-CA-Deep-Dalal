"""Credit rating + default-history check for a listed company.

Sources (all public):
  * Screener.in company page: list of credit-rating rationale documents (agency, date,
    link), headline financials (borrowings, interest, net worth, market cap) and its
    machine-generated "cons" (low interest coverage, pledged shares, ...).
  * The rating agencies' own rationale documents (CARE / CRISIL / ICRA / Acuite /
    Infomerics / Brickwork ...), read as text (PDF via `pdftotext`):
      - current grade, outlook, "Issuer Not Cooperating"
      - rating-history annexure: any "D" grade = a past default on bank loans / debt
      - sentences that report delays, defaults, NPA, one-time settlement, insolvency.

Everything found is returned as evidence (text + source link) so the user can judge.
"""
import html
import os
import re
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request

VERSION = 3  # bump when parsing changes so cached profiles are rebuilt
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
AGENCY = r"(?:CARE|\[ICRA\]|ICRA|CRISIL|IND|ACUITE|Acuite|IVR|BWR|Brickwork|INFOMERICS|PR)"
LT = r"(AAA|AA|A|BBB|BB|B|C|D)([+-])?"
ST = r"(A1|A2|A3|A4)(\+)?"
RANK = {"AAA": 1, "AA": 2, "A": 3, "BBB": 4, "BB": 5, "B": 6, "C": 7, "D": 8}
ST_TO_LT = {"A1": "A", "A2": "BBB", "A3": "BB", "A4": "B"}
AGENCY_NAMES = {"care": "CARE", "crisil": "CRISIL", "icra": "ICRA", "indiaratings": "India Ratings",
                "acuite": "Acuite", "infomerics": "Infomerics", "brickwork": "Brickwork", "bcrisp": "Brickwork"}


def _fetch(url, binary=False, tries=3):
    url = urllib.parse.quote(url, safe=":/?=&%#+~,;@!$*()'[]")
    hdr = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-IN,en;q=0.9",
           "Referer": "https://www.screener.in/"}
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=40) as r:
                b = r.read()
                return b if binary else b.decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            code = getattr(e, "code", None)
            if code == 429:
                time.sleep(8 * (i + 1))
                continue
            if code in (403, 404, 410):
                return None
            time.sleep(2 * (i + 1))
    return None


def _clean(s):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()


def _num(s):
    s = (s or "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


# ------------------------------------------------------------------ screener
def screener(ident):
    page = _fetch(f"https://www.screener.in/company/{urllib.parse.quote(ident)}/")
    if not page or "id=\"top-ratios\"" not in page:
        return None
    out = {"url": f"https://www.screener.in/company/{ident}/", "ratingDocs": [], "cons": [], "pros": []}
    m = re.search(r'class="documents credit-ratings.*?</ul>', page, re.S)
    if m:
        for href, body in re.findall(r'<a href="([^"]+)"[^>]*>(.*?)</a>', m.group(0), re.S):
            sub = re.search(r'<div[^>]*>(.*?)</div>', body, re.S)
            meta = _clean(sub.group(1)) if sub else ""
            mm = re.match(r"(.*?)\s+from\s+(\w+)$", meta)
            out["ratingDocs"].append({"url": html.unescape(href), "title": _clean(re.sub(r"<div.*", "", body, flags=re.S)),
                                      "when": mm.group(1) if mm else meta, "agency": (mm.group(2) if mm else "").lower()})
    for cls in ("pros", "cons"):
        m = re.search(rf'class="{cls}".*?<ul>(.*?)</ul>', page, re.S)
        if m:
            out[cls] = [_clean(x) for x in re.findall(r"<li>(.*?)</li>", m.group(1), re.S)]
    top = {}
    m = re.search(r'id="top-ratios"(.*?)</ul>', page, re.S)
    if m:
        for li in re.findall(r"<li.*?</li>", m.group(1), re.S):
            name = re.search(r'class="name">(.*?)</span>', li, re.S)
            nums = re.findall(r'class="number">(.*?)</span>', li, re.S)
            if name and nums:
                top[_clean(name.group(1))] = [_num(_clean(n)) for n in nums]
    out["marketCapCr"] = (top.get("Market Cap") or [None])[0]
    out["bookValue"] = (top.get("Book Value") or [None])[0]
    out["roce"] = (top.get("ROCE") or [None])[0]
    out["roe"] = (top.get("ROE") or [None])[0]

    def table(sec_id):
        s = page.find(f'id="{sec_id}"')
        if s < 0:
            return [], {}
        seg = page[s:]
        tb = re.search(r"<table.*?</table>", seg, re.S)
        if not tb:
            return [], {}
        tb = tb.group(0)
        hdr = [_clean(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", tb, re.S)][1:]
        rows = {}
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tb, re.S):
            cells = [_clean(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            if cells:
                key = re.sub(r"[^A-Za-z ]", "", cells[0]).strip()
                rows[key] = [_num(c.replace("%", "")) for c in cells[1:]]
        return hdr, rows

    ph, pl = table("profit-loss")
    bh, bs = table("balance-sheet")
    last = lambda rows, k: next((v for v in reversed(rows.get(k) or []) if v is not None), None)  # noqa: E731
    fin = {"financialCo": "Financing Profit" in pl or "Revenue" in pl and "Sales" not in pl,
           "period": bh[-1] if bh else None,
           "equity": last(bs, "Equity Capital"), "reserves": last(bs, "Reserves"),
           "borrowings": last(bs, "Borrowings"), "interest": last(pl, "Interest"),
           "opProfit": last(pl, "Operating Profit"), "otherIncome": last(pl, "Other Income"),
           "netProfit": last(pl, "Net Profit"),
           "borrowHist": [v for v in (bs.get("Borrowings") or [])][-5:], "borrowHdr": bh[-5:]}
    if fin["equity"] is not None and fin["reserves"] is not None:
        fin["netWorth"] = fin["equity"] + fin["reserves"]
    if fin.get("netWorth") and fin["borrowings"] is not None and fin["netWorth"] > 0:
        fin["debtEquity"] = round(fin["borrowings"] / fin["netWorth"], 2)
    if fin["interest"] and fin["opProfit"] is not None and not fin["financialCo"]:
        fin["icr"] = round((fin["opProfit"] + (fin["otherIncome"] or 0)) / fin["interest"], 2)
    out["fin"] = fin
    for c in out["cons"]:
        m = re.search(r"pledged ([\d.]+)%", c)
        if m:
            out["pledgePct"] = float(m.group(1))
    return out


# ----------------------------------------------------------- rating documents
def doc_text(url, _depth=0):
    b = _fetch(url, binary=True)
    if not b:
        return None
    if b[:4] == b"%PDF":
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "r.pdf")
            open(p, "wb").write(b)
            try:
                r = subprocess.run(["pdftotext", "-layout", p, "-"], capture_output=True, timeout=60)
                return r.stdout.decode("utf-8", "replace")
            except (OSError, subprocess.TimeoutExpired):
                return None
    t = b.decode("utf-8", "replace")
    # Some agencies (e.g. ICRA) serve an HTML shell that embeds the rationale PDF in an
    # iframe; follow that embedded document (the same link the page offers to open).
    if _depth == 0:
        m = re.search(r'<iframe[^>]+(?:data-pdf-url|src)="([^"]*(?:[Pp]df|Rational)[^"]*)"', t)
        if m:
            inner = doc_text(urllib.parse.urljoin(url, html.unescape(m.group(1))), _depth=1)
            if inner and len(inner) > 500:
                return inner
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<br\s*/?>|</(p|tr|div|li|h\d)>", "\n", t, flags=re.I)
    return html.unescape(re.sub(r"<[^>]+>", " ", t))


def _grades(text):
    """All agency grade tokens in text -> list of (pos, lt_grade, raw)."""
    out = []
    for m in re.finditer(AGENCY + r"\s*\(?\s*" + r"(AAA|AA|A1|A2|A3|A4|A|BBB|BB|B|C|D)([+-])?(?![A-Za-z0-9])", text):
        g, mod = m.group(1), m.group(2) or ""
        lt = ST_TO_LT.get(g, g)
        if g == "D" or lt in RANK:
            out.append((m.start(), lt, (m.group(0).strip() if g not in ST_TO_LT else m.group(0).strip()), g in ST_TO_LT, mod))
    return out


NEG_CTX = re.compile(r"\b(no|not|nil|without|never|absence|timely|regular in)\b", re.I)
BOILER = re.compile(r"(polic|criteria|definition|methodolog|www\.|disclaimer|rating scale|probability of default|"
                    r"Status of non-cooperation with previous CRA: (?:Not Applicable|None))", re.I)
FLAGS = [
    ("default", re.compile(r"\b(defaulted|default(?:s)? (?:in|on) (?:the )?(?:payment|repayment|servicing|debt)|"
                           r"delay(?:s|ed)? in (?:debt )?servicing|delay(?:s|ed)? in (?:the )?(?:repayment|payment of (?:interest|principal))|"
                           r"overdue|irregular(?:ity|ities)? in|devolvement)", re.I)),
    ("npa", re.compile(r"\b(NPA|non[- ]performing asset|special mention account|\bSMA[- ]?[0-2]\b)", re.I)),
    ("ots", re.compile(r"\b(one[- ]time settlement|\bOTS\b|restructur(?:ed|ing) (?:of )?(?:its )?(?:debt|loans|facilities))", re.I)),
    ("insolvency", re.compile(r"\b(CIRP|corporate insolvency|insolvency (?:and bankruptcy|resolution|proceedings)|NCLT|"
                              r"IBC|liquidation|resolution plan)", re.I)),
]


def parse_rating(text, url, agency_hint, when):
    t = text or ""
    # current-rating table = text before the rationale section
    cut = re.search(r"Rationale|Key Rating Drivers|Detailed Rationale|Summary of rating action", t, re.I)
    head = t[: cut.start()] if cut and cut.start() > 200 else t[:4000]
    tail = t[len(head):]
    cur = _grades(head)
    if not cur:
        # e.g. ICRA web pages carry "Rationale" in their header, so the table window is empty:
        # fall back to the document body up to the rating-history annexure
        hist = re.search(r"Annexure[- ]?(?:II|2)|Rating history|History of rating", t, re.I)
        body = t[: hist.start()] if hist and hist.start() > 500 else t[:15000]
        cur = _grades(body)
        head, tail = body, t[len(body):]
    lt = [g for g in cur if not g[3]] or cur
    res = {"url": url, "agency": AGENCY_NAMES.get(agency_hint, agency_hint.upper() or None), "when": when,
           "grade": None, "raw": None, "rank": None, "outlook": None, "inc": False, "withdrawn": False,
           "currentD": False, "historyD": [], "flags": []}
    if lt:
        # the grade carried by most facilities; ties -> the weaker one (conservative)
        cnt = {}
        for g in lt:
            cnt[(g[1], g[4])] = cnt.get((g[1], g[4]), 0) + 1
        top = max(cnt.values())
        cands = [g for g in lt if cnt[(g[1], g[4])] == top]
        worst = max(cands, key=lambda g: (RANK.get(g[1], 0), g[4] == "-", -(g[4] == "+")))
        res["grade"] = worst[1] + worst[4]
        res["raw"] = re.sub(r"\s+", " ", worst[2])
        res["rank"] = RANK.get(worst[1])
        res["currentD"] = any(g[1] == "D" for g in lt)
        res["shortTermOnly"] = all(g[3] for g in lt)
    if re.search(r"withdrawn", head, re.I) and not lt:
        res["withdrawn"] = True
    om = re.search(r"\b(Stable|Positive|Negative|Developing)\b", head) or \
        re.search(r"Outlook\s*[:\-]\s*(Stable|Positive|Negative|Developing)", t, re.I) or \
        re.search(r"Rating Watch with (Negative|Positive|Developing)", t, re.I)
    if om:
        res["outlook"] = om.group(1).capitalize()
    res["inc"] = bool(re.search(r"ISSUER NOT COOPERATING|\bINC\b", head, re.I))
    res["incHistory"] = bool(re.search(r"ISSUER\s+NOT|did not cooperate|non-?cooperation by the (?:company|issuer)", tail, re.I))
    # rating history: D grades after the current table
    for pos, g, raw, st, mod in _grades(tail):
        if g == "D":
            near = tail[pos: pos + 700]
            dm = re.search(r"\((\d{1,2}-[A-Za-z]{3}-\d{2,4})\)", near) or re.search(r"(\d{1,2}-[A-Za-z]{3}-\d{2,4})", near)
            item = {"raw": re.sub(r"\s+", " ", raw), "date": dm.group(1) if dm else None}
            if not any(h["raw"] == item["raw"] and h["date"] == item["date"] for h in res["historyD"]) and \
                    not (item["date"] is None and res["historyD"]):
                res["historyD"].append(item)
    # flag sentences
    flat = re.sub(r"\s+", " ", t)
    seen = set()
    for sent in re.split(r"(?<=[.;])\s+(?=[A-Z(])", flat):
        if len(sent) > 450 or BOILER.search(sent):
            continue
        if sum(ch.isdigit() for ch in sent) > len(sent) * 0.12:  # table fragments
            continue
        for key, rx in FLAGS:
            m = rx.search(sent)
            if not m:
                continue
            pre = sent[max(0, m.start() - 60): m.start()]
            if key in ("default", "npa", "ots") and NEG_CTX.search(pre):
                continue
            s = sent.strip()[:320]
            if s[:80] in seen:
                continue
            seen.add(s[:80])
            res["flags"].append({"type": key, "text": s})
    res["flags"] = res["flags"][:8]
    return res


def credit_profile(nse=None, bse=None, isin=None, log=print, max_docs=3):
    ident = nse or bse
    if not ident:
        return None
    sc = screener(ident)
    if sc is None and nse and bse:
        time.sleep(3)
        sc = screener(bse)
    if sc is None:
        log("  credit: screener page not found for", ident)
        return None
    time.sleep(2.5)
    docs = []
    for d in sc["ratingDocs"][:max_docs]:
        txt = doc_text(d["url"])
        time.sleep(1.2)
        if not txt or len(txt) < 300:
            docs.append({"url": d["url"], "agency": AGENCY_NAMES.get(d["agency"], d["agency"].upper()),
                         "when": d["when"], "unreadable": True})
            continue
        docs.append(parse_rating(txt, d["url"], d["agency"], d["when"]))
    current = next((d for d in docs if d.get("grade")), None)
    past_d = []
    for d in docs:
        for h in d.get("historyD", []):
            past_d.append({**h, "agency": d.get("agency"), "url": d["url"]})
        if d.get("currentD") and d is not current:
            past_d.append({"raw": d.get("raw"), "date": d.get("when"), "agency": d.get("agency"), "url": d["url"]})
    fin_co = bool((sc.get("fin") or {}).get("financialCo"))
    flags = []
    for d in docs:
        for f in d.get("flags", []):
            if fin_co and f["type"] == "npa":  # a lender's NPAs are its borrowers' defaults
                continue
            flags.append({**f, "agency": d.get("agency"), "when": d.get("when"), "url": d["url"]})
    prof = {
        "fetchedAt": int(time.time()),
        "v": VERSION,
        "screenerUrl": sc["url"],
        "marketCapCr": sc.get("marketCapCr"),
        "bookValue": sc.get("bookValue"),
        "roce": sc.get("roce"), "roe": sc.get("roe"),
        "fin": sc.get("fin"),
        "pledgePct": sc.get("pledgePct"),
        "cons": sc.get("cons", [])[:8],
        "pros": sc.get("pros", [])[:6],
        "rating": current,
        "docs": [{k: d.get(k) for k in ("agency", "when", "url", "grade", "raw", "outlook", "inc", "withdrawn", "unreadable")}
                 for d in docs] + [{"agency": AGENCY_NAMES.get(d["agency"], d["agency"].upper()), "when": d["when"],
                                    "url": d["url"], "notRead": True} for d in sc["ratingDocs"][max_docs:max_docs + 5]],
        "pastDefaults": past_d[:10],
        "flags": flags[:12],
        "unrated": not sc["ratingDocs"],
        "incHistory": any(d.get("incHistory") for d in docs),
    }
    log(f"  credit: {ident} rating={current and current.get('raw')} docs={len(docs)} pastD={len(past_d)} flags={len(flags)}")
    return prof
