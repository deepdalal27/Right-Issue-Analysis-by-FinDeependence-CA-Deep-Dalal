"""Temporary probe v2: Screener public company pages (credit-rating docs, announcements, debt)."""
import os, urllib.request
os.makedirs("probe", exist_ok=True)
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
     "Accept": "text/html", "Accept-Language": "en-IN,en;q=0.9"}
def get(u):
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=40) as r:
            return r.status, r.geturl(), r.read().decode("utf-8", "replace")
    except Exception as e:
        return getattr(e, "code", -1), u, str(e)
log = []
for code in ["517320", "532776", "532532", "SHIVAMAUTO", "500180"]:
    s, final, t = get(f"https://www.screener.in/company/{code}/")
    open(f"probe/scr_{code}.html", "w").write(t)
    log.append(f"{s} {len(t)} {code} -> {final}")
open("probe/log.txt", "w").write("\n".join(log)); print("\n".join(log))
