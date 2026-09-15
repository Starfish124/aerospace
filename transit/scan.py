"""Sector -> results CSV. Streams one light curve at a time so the disk never fills. Resumable."""
import csv
import re
import urllib.request
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

warnings.filterwarnings("ignore")
import lightkurve as lk

from transit.fetch import DATA, retry
from transit.search import search_full
import json
import numpy as np
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
        retry(lambda: urllib.request.urlretrieve(url, path))
        lc = lk.read(path, quality_bitmask="default").remove_nans().normalize()
        cands, flat, periods, power = search_full(lc, top=1)
        c = cands[0]
        v = vet(f"TIC{tic}", c)
        row.update(period=round(c.period, 5), t0=round(c.t0, 4), duration=round(c.duration, 3),
                   depth=round(c.depth * 1e6), snr=round(c.snr, 1), label=v.label, reasons="; ".join(v.reasons))
        evidence(tic, sector, row, c, flat, periods, power)
    except Exception as e:  # one bad star must not stop a 16k-star night
        row.update(label="ERROR", reasons=f"{type(e).__name__}: {e}"[:200])
    finally:
        path.unlink(missing_ok=True)
    return row


def _thin(x, y, n):
    """Downsample two arrays to ~n points for the page."""
    step = max(1, len(x) // n)
    return [round(float(a), 5) for a in x[::step]], [round(float(b), 6) for b in y[::step]]


def evidence(tic, sector, row, c, flat, periods, power):
    """What the search saw for this star: light curve, periodogram, fold. Written for the sky page.
    Always to data/current.json (the star being looked at now); kept in data/stars/ for KNOWN and NEW."""
    t, f = flat.time.value, flat.flux.value
    phase = ((t - c.t0 + 0.5 * c.period) % c.period) / c.period - 0.5
    order = np.argsort(phase)
    ph, pf = phase[order], f[order]
    nb = 200  # binned fold
    edges = np.linspace(-0.5, 0.5, nb + 1)
    idx = np.clip(np.digitize(ph, edges) - 1, 0, nb - 1)
    binned = [float(np.nanmedian(pf[idx == i])) if np.any(idx == i) else None for i in range(nb)]
    lt, lf = _thin(t, f, 800)
    pp, pw = _thin(periods, power, 500)
    doc = {"tic": tic, "sector": sector, "row": row, "sde": round(c.sde, 2), "n_transits": c.n_transits,
           "lc": {"t": lt, "f": lf}, "pgram": {"p": pp, "w": pw},
           "fold": {"phase": [round(float(x), 4) for x in (edges[:-1] + edges[1:]) / 2], "f": binned,
                    "duration_phase": round(c.duration / c.period, 4)}}
    tmp = DATA / "current.json.tmp"
    tmp.write_text(json.dumps(doc))
    tmp.replace(DATA / "current.json")
    if row.get("label") in ("KNOWN", "NEW"):
        (DATA / "stars").mkdir(exist_ok=True)
        (DATA / "stars" / f"{tic}.json").write_text(json.dumps(doc))


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
                    print(f"{i:6d}/{len(todo)}  TIC{row['tic']:<12} {row['label']:9s} {row.get("reasons","")[:70]}", flush=True)
    return out
