"""One-off probe v2: API endpoints + detail page."""
import os, re, json, urllib.request
os.makedirs("probe", exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
      "Accept": "*/*", "Origin": "https://www.chittorgarh.com", "Referer": "https://www.chittorgarh.com/"}
def get(u):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30)
        return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return getattr(e, "code", -1), str(e)
log = []
def save(name, u):
    s, t = get(u)
    open(f"probe/{name}", "w").write(t)
    log.append(f"{s} {len(t)} {name} {u}"); print(log[-1])
    return s, t
B = "https://webnodejs.chittorgarh.com/cloud/report/data-read"
n = 0
for rid in (75, 197, 74):
    for suf in ["1/1/2026/2026-27/0/", "1/1/2026/2026-27/0/all", "1/1/2026/2026-27/0/mainboard", "1/1/0/0/0/", "1/1/2026/2025-26/0/all"]:
        n += 1; save(f"api{rid}_{n}.json", f"{B}/{rid}/{suf}")
# find JS chunk containing data-read pattern
s, t = get("https://www.chittorgarh.com/report/latest-rights-issue-in-india/75/")
chunks = sorted(set(re.findall(r'(/_next/static/chunks/[^"\\]+\.js)', t)))
hits = []
for c in chunks:
    s2, js = get("https://www.chittorgarh.com" + c)
    for m in re.finditer(r'data-read|rights-issue/', js):
        hits.append(c + " :: " + js[max(0, m.start()-300):m.start()+300])
open("probe/jshits.txt", "w").write("\n\n".join(hits[:40]))
# calendar page detail links
s, cal = get("https://www.chittorgarh.com/calendar/rights-issue-calendar/4/")
ev = sorted(set(re.findall(r'https://www\.chittorgarh\.com/rights-issue-calendar-events/[^"#]+', cal)))
open("probe/events.txt", "w").write("\n".join(ev))
if ev: save("event1.html", ev[0])
allr = sorted(set(re.findall(r'(?:https://www\.chittorgarh\.com)?/rights-issue/[a-z0-9-]+/\d+/', cal + t)))
open("probe/rlinks.txt", "w").write("\n".join(allr))
for i, u in enumerate(allr[:2]):
    save(f"rdetail{i}.html", u if u.startswith("http") else "https://www.chittorgarh.com" + u)
open("probe/log.txt", "w").write("\n".join(log))
