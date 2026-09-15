"""Target -> light curve. Cached under data/, capped at 2 GB."""
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")  # lightkurve/astropy are chatty
import lightkurve as lk

DATA = Path(__file__).resolve().parent.parent / "data"
CAP_BYTES = 2 * 1024**3


def _enforce_cap(root: Path = DATA):
    """Delete oldest files until the cache is under CAP_BYTES.
    ponytail: full walk every call; fine for a 2 GB folder, index it if scans slow down."""
    files = [p for p in root.rglob("*") if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    for p in sorted(files, key=lambda p: p.stat().st_atime):
        if total <= CAP_BYTES:
            break
        total -= p.stat().st_size
        p.unlink()


def retry(fn, tries=3, wait=5):
    """MAST drops connections now and then; three tries with a pause covers it."""
    for i in range(tries):
        try:
            return fn()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(wait)


def fetch(target: str, sectors=None) -> lk.LightCurve:
    """Download every SPOC 2-min light curve for a target and stitch them into one.
    `target` is like 'TIC100100827'. `sectors` limits which sectors, None = all."""
    DATA.mkdir(exist_ok=True)
    _enforce_cap()
    result = retry(lambda: lk.search_lightcurve(target, author="SPOC", cadence=120, sector=sectors))
    if len(result) == 0:
        raise ValueError(f"no SPOC 2-min light curve for {target}")
    lcs = retry(lambda: result.download_all(download_dir=str(DATA), quality_bitmask="default"))
    # remove_nans + normalize per sector, then stitch so sectors share a baseline
    return lcs.stitch(lambda lc: lc.remove_nans().normalize())


if __name__ == "__main__":  # self-check, needs network
    lc = fetch("TIC100100827", sectors=2)
    assert len(lc) > 10_000 and abs(lc.flux.value.mean() - 1) < 0.01
    print("ok", len(lc), "points")
