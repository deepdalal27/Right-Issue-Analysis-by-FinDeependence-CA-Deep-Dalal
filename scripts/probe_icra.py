"""Temporary probe: what does ICRA's embedded viewer URL return?"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import credit
os.makedirs("probe", exist_ok=True)
b = credit._fetch("https://www.icra.in/Rating/ShowRationalReportFilePdfViewer/139357", binary=True) or b"NONE"
open("probe/viewer_head.txt", "w").write(f"len={len(b)} head={b[:12]!r}\n" + b[:60000].decode("utf-8", "replace"))
