"""Temporary probe v3: Screener announcement tabs, rating PDFs, known defaulters."""
import os, re, subprocess, time, urllib.request
os.makedirs("probe", exist_ok=True)
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
     "Accept": "*/*", "Accept-Language": "en-IN,en;q=0.9", "Referer": "https://www.screener.in/"}
log = []
def get(u, binary=False):
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=40) as r:
                b = r.read(); return r.status, (b if binary else b.decode("utf-8", "replace"))
        except Exception as e:
            c = getattr(e, "code", -1)
            if c == 429: time.sleep(6 * (i + 1)); continue
            return c, (b"" if binary else str(e))
    return 429, (b"" if binary else "")
def save(name, u, binary=False):
    s, t = get(u, binary); open("probe/" + name, "wb" if binary else "w").write(t)
    log.append(f"{s} {len(t)} {name} {u}"); print(log[-1]); time.sleep(3); return s, t
save("imp_2993.html", "https://www.screener.in/announcements/important/2993/")
save("search_2993.html", "https://www.screener.in/announcements/search/2993/")
save("search_2993_q.html", "https://www.screener.in/announcements/search/2993/?q=default")
for sym in ["RELINFRA", "JPASSOCIAT", "IDEA", "HDFCBANK"]:
    s, t = save(f"scr_{sym}.html", f"https://www.screener.in/company/{sym}/")
    m = re.search(r'credit-ratings.*?</ul>', t, re.S)
    links = re.findall(r'href="([^"]+)"', m.group(0)) if m else []
    log.append(f"  ratings links: {links[:4]}")
    for j, l in enumerate(links[:2]):
        s2, b = save(f"rt_{sym}_{j}.bin", l, binary=True)
        if b[:4] == b"%PDF":
            open(f"probe/rt_{sym}_{j}.pdf", "wb").write(b)
            r = subprocess.run(["pdftotext", "-layout", f"probe/rt_{sym}_{j}.pdf", f"probe/rt_{sym}_{j}.txt"], capture_output=True)
            log.append(f"  pdftotext rc={r.returncode} {r.stderr[:100]}")
        os.remove(f"probe/rt_{sym}_{j}.bin")
s, b = save("care_shivam.bin", "https://www.careratings.com/upload/CompanyFiles/PR/202601140125_Shivam_Autotech_Limited.pdf", True)
if b[:4] == b"%PDF":
    open("probe/care_shivam.pdf", "wb").write(b); subprocess.run(["pdftotext", "-layout", "probe/care_shivam.pdf", "probe/care_shivam.txt"])
os.remove("probe/care_shivam.bin")
open("probe/log.txt", "w").write("\n".join(log))
