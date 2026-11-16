"""Temporary probe: dump the text of one ICRA rationale page."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import credit
os.makedirs("probe", exist_ok=True)
t = credit.doc_text("https://www.icra.in/Rationale/ShowRationaleReport/?Id=139357") or "NONE"
open("probe/icra.txt", "w").write(t)
raw = credit._fetch("https://www.icra.in/Rationale/ShowRationaleReport/?Id=139357") or "NONE"
open("probe/icra_raw.html", "w").write(raw[:200000])
print(len(t), len(raw))
