"""Sector -> results CSV. Streams one light curve at a time so the disk never fills. Resumable."""
import csv
import re
import urllib.request
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

warnings.filterwarnings("ignore")
import lightkurve as lk

from transit.fetch import DATA
from transit.search import search
from transit.vet import vet, toi_table

SCRIPT_URL = "https://archive.stsci.edu/missions/tess/download_scripts/sector/tesscurl_sector_{}_lc.sh"
FIELDS = ["tic", "sector", "period", "t0", "duration", "depth", "snr", "label", "reasons"]


def targets(sector: int) -> list[tuple[str, str]]:
    """[(tic, url), ...] for every 2-min target in a sector, from MAST's own bulk-download script."""
    script = DATA / f"sector_{sector}.sh"
    DATA.mkdir(exist_ok=True)
    if not script.exists():
        urllib.request.urlretrieve(SCRIPT_URL.format(sector), script)
    out = []
    for line in script.read_text().splitlines():
        m = re.search(r"-0*(\d+)-0120-s_lc\.fits (https://\S+)", line)
        if m:
            out.append((m.group(1), m.group(2)))
    return out


def one(tic: str, url: str, sector: int) -> dict:
    """fetch -> search -> vet -> row, then delete the file."""
    path = DATA / f"scan_{sector}_{tic}.fits"
    row = {"tic": tic, "sector": sector}
    try:
        urllib.request.urlretrieve(url, path)
        lc = lk.read(path, quality_bitmask="default").remove_nans().normalize()
        c = search(lc, top=1)[0]
        v = vet(f"TIC{tic}", c)
        row.update(period=round(c.period, 5), t0=round(c.t0, 4), duration=round(c.duration, 3),
                   depth=round(c.depth * 1e6), snr=round(c.snr, 1), label=v.label, reasons="; ".join(v.reasons))
    except Exception as e:  # one bad star must not stop a 16k-star night
        row.update(label="ERROR", reasons=f"{type(e).__name__}: {e}"[:200])
    finally:
        path.unlink(missing_ok=True)
    return row


def scan(sector: int, limit: int | None = None, workers: int = 4) -> Path:
    out = DATA / f"scan_{sector}.csv"
    done = set()
    if out.exists():
        with out.open() as f:
            done = {r["tic"] for r in csv.DictReader(f)}
    todo = [(t, u) for t, u in targets(sector) if t not in done][:limit]
    toi_table()  # warm the catalog once, not per thread
    print(f"sector {sector}: {len(done)} done, {len(todo)} to go")
    with out.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if not done:
            w.writeheader()
        # ponytail: threads, not processes; BLS is C and mostly releases the GIL, downloads dominate anyway
        with ThreadPoolExecutor(workers) as ex:
            for i, row in enumerate(ex.map(lambda tu: one(*tu, sector), todo), 1):
                w.writerow(row); f.flush()
                if i % 50 == 0 or row["label"] == "NEW":
                    print(f"{i:6d}/{len(todo)}  TIC{row['tic']:<12} {row['label']:9s} {row.get('reasons','')[:70]}")
    return out
