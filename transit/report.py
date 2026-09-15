"""Scan CSVs -> plain-text report (ADR-005). Also the nightly entry point."""
import csv
import subprocess
from collections import Counter
from datetime import date
from pathlib import Path

from transit.fetch import DATA
from transit.scan import scan, targets

REPORTS = Path(__file__).resolve().parent.parent / "reports"


def report() -> str:
    lines = [f"aerospace transit report {date.today()}", ""]
    new = []
    looks = DATA / "looks.csv"
    over = {r["tic"]: r for r in csv.DictReader(looks.open())} if looks.exists() else {}
    for csvf in sorted(DATA.glob("scan_*.csv")):
        rows = list(csv.DictReader(csvf.open()))
        for r in rows:
            if r["tic"] in over:
                r["label"] = over[r["tic"]]["label"]; r["reasons"] = f"look {over[r['tic']]['recovered']} sectors: " + over[r["tic"]]["reasons"]
        sector = csvf.stem.split("_")[1]
        c = Counter(r["label"] for r in rows)
        total = len(targets(int(sector)))
        lines.append(f"sector {sector}: {len(rows)}/{total} scanned  " + "  ".join(f"{k} {v}" for k, v in sorted(c.items())))
        new += [r for r in rows if r["label"] == "NEW"]
    lines += ["", f"NEW candidates ({len(new)}), strongest first:"]
    for r in sorted(new, key=lambda r: -float(r["snr"]))[:10]:
        lines.append(f"  TIC{r['tic']:<12} s{r['sector']}  P={float(r['period']):.4f} d  depth={r['depth']} ppm  snr={r['snr']}  {r['reasons']}")
    if not new:
        lines.append("  none")
    text = "\n".join(lines)
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / f"{date.today()}.txt").write_text(text + "\n")
    return text


def nightly():
    """Scan the lowest sector not yet complete, then write and commit the report. No LLM (ADR-002)."""
    sector = 1
    while True:
        csvf = DATA / f"scan_{sector}.csv"
        if not csvf.exists() or sum(1 for _ in csvf.open()) - 1 < len(targets(sector)):
            break
        sector += 1
    scan(sector)
    print(report())
    root = REPORTS.parent
    subprocess.run(["git", "add", "reports"], cwd=root)
    subprocess.run(["git", "commit", "-qm", f"nightly report {date.today()}"], cwd=root)
    subprocess.run(["git", "push", "-q"], cwd=root)  # may fail under launchd without credentials; report is still committed
