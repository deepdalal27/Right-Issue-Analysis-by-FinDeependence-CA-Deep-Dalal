"""One-off probe: download sample pages so the parser can be written against real HTML."""
import os, re, json, urllib.request, urllib.parse
os.makedirs("probe", exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
      "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"}
def get(u):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30)
        return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return getattr(e, "code", -1), str(e)
def save(name, u):
    s, t = get(u)
    open(f"probe/{name}", "w").write(t)
    print(s, len(t), u)
    return t
home = save("home.html", "https://www.chittorgarh.com/")
links = sorted(set(re.findall(r'href="(https://www\.chittorgarh\.com/[^"]*right[^"]*)"', home, re.I)))
links += sorted(set("https://www.chittorgarh.com" + l for l in re.findall(r'href="(/[^"]*right[^"]*)"', home, re.I)))
open("probe/links.txt", "w").write("\n".join(links))
print("\n".join(links))
cands = links + ["https://www.chittorgarh.com/rights-issue/", "https://www.chittorgarh.com/report/rights-issue-list-in-india/"]
seen = set(); i = 0
for u in cands:
    if u in seen or i > 12: continue
    seen.add(u); i += 1
    t = save(f"page{i}.html", u)
    for d in sorted(set(re.findall(r'(https://www\.chittorgarh\.com/rights-issue/[^"\s]+/\d+/|/rights-issue/[^"\s]+/\d+/)', t)))[:3]:
        if d not in seen and i <= 12:
            seen.add(d); i += 1
            save(f"detail{i}.html", d if d.startswith("http") else "https://www.chittorgarh.com" + d)
    for rid in sorted(set(re.findall(r'data-read/(\d+)/', t)))[:5]:
        print("reportid", rid, u)
save("yahoo.json", "https://query1.finance.yahoo.com/v8/finance/chart/RELIANCE.NS?range=5d&interval=1d")
