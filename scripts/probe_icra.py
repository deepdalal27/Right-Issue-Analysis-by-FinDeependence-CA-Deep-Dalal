"""Temporary probe: full credit profile for Natco (ICRA) after the iframe fix."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import credit
os.makedirs("probe", exist_ok=True)
p = credit.credit_profile(nse="NATCOPHARM")
open("probe/natco.json", "w").write(json.dumps({"rating": p and p["rating"], "docs": p and p["docs"], "flags": p and p["flags"], "pastD": p and p["pastDefaults"]}, indent=1))
