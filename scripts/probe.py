"""One-off probe v3: public detail + subscription pages."""
import os, urllib.request
os.makedirs("probe", exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
def get(u):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30)
        return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return getattr(e, "code", -1), str(e)
log = []
def save(name, u):
    s, t = get(u); open(f"probe/{name}", "w").write(t)
    log.append(f"{s} {len(t)} {name} {u}"); print(log[-1])
C = "https://www.chittorgarh.com"
save("d593.html", C + "/rights-issue/magnus-steel-infra-rights-issue-november-2026/593/")
save("d600.html", C + "/rights-issue/kanel-industries-rights-issue-nov-2026/600/")
for p in ["rights-issue-subscription-status", "rights-issue-subscription"]:
    save(f"s_{p}.html", f"{C}/{p}/magnus-steel-infra-rights-issue-november-2026/593/")
open("probe/log.txt", "w").write("\n".join(log))
