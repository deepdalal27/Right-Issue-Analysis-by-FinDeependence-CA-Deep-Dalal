"""Temporary probe: sample BSE corporate announcements to design the credit/default parser."""
import json, os, urllib.request, urllib.parse
from datetime import date, timedelta
os.makedirs("probe", exist_ok=True)
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
     "Referer": "https://www.bseindia.com/", "Origin": "https://www.bseindia.com", "Accept": "application/json"}
def get(u):
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=40) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return getattr(e, "code", -1), str(e)
to = date.today(); fr = to - timedelta(days=3*365)
log = []
for code in ["517320", "541741", "532776", "500236", "532532", "500390", "500180", "519242"]:
    q = dict(pageno=1, strCat=-1, strPrevDate=fr.strftime("%Y%m%d"), strScrip=code, strSearch="P",
             strToDate=to.strftime("%Y%m%d"), strType="C", subcategory=-1)
    u = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w?" + urllib.parse.urlencode(q)
    s, t = get(u)
    open(f"probe/bse_{code}.json", "w").write(t)
    log.append(f"{s} {len(t)} {code}")
open("probe/log.txt", "w").write("\n".join(log)); print("\n".join(log))
