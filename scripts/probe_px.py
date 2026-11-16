"""Temporary probe: ground-truth prices for stocks whose sources disagree."""
import json, os, sys, time, re, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import credit
os.makedirs("probe", exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
out = {}
for ysym, scr in [("IEML.NS", "IEML"), ("URBAN.NS", "URBAN"), ("NOVARTIND.NS", "NOVARTIND"), ("PARTYCRUS.NS", "PARTYCRUS"),
                  ("RAJGOR.NS", "RAJGOR"), ("SUNREST.NS", "SUNREST")]:
    r = {}
    for rng in ("1mo",):
        u = f"https://query1.finance.yahoo.com/v8/finance/chart/{ysym}?range={rng}&interval=1d&events=div%2Csplit"
        try:
            j = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read())
            res = j["chart"]["result"][0]; q = res["indicators"]["quote"][0]
            r["meta"] = {k: res["meta"].get(k) for k in ("regularMarketPrice", "chartPreviousClose", "previousClose", "regularMarketDayHigh", "regularMarketDayLow", "regularMarketVolume", "fiftyTwoWeekHigh", "fiftyTwoWeekLow", "regularMarketTime", "symbol")}
            r["events"] = res.get("events")
            r["last5"] = list(zip(res["timestamp"][-5:], q["close"][-5:], q["volume"][-5:]))
            r["adjclose_last"] = (res["indicators"].get("adjclose") or [{}])[0].get("adjclose", [None])[-3:]
        except Exception as e:
            r["err"] = str(e)
    sc = credit.screener(scr)
    if sc:
        r["screener"] = {"price": sc.get("price"), "mcap": sc.get("marketCapCr"), "fv": sc.get("faceValue"), "equity": (sc.get("fin") or {}).get("equity")}
    out[ysym] = r
    time.sleep(3)
open("probe/px.json", "w").write(json.dumps(out, indent=1))
