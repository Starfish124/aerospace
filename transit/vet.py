"""Candidate -> verdict. Kills false positives, then asks the TOI catalog if it is Known or New."""
import time
from functools import lru_cache
import urllib.request
from dataclasses import dataclass

import pandas as pd

from transit.fetch import DATA
from transit.search import Candidate

TOI_URL = "https://exofop.ipac.caltech.edu/tess/download_toi.php?sort=toi&output=csv"
TOI_CSV = DATA / "toi.csv"
SNR_FLOOR = 7.0
SDE_FLOOR = 8.0      # calibrated 2026-09-15: WASP-18 b 9.3, Pi Men c 10.0; 14 false positives all < 7.2
MIN_TRANSITS = 3     # one or two dips is a glitch or a single event, not a period
SIGMA = 3.0
# Relative thresholds matter more than sigma: at SNR 600 a 10 % odd/even wobble is 40σ but still a planet.
# Eclipsing binaries show odd/even off by ~2x and secondaries of tens of percent.
ODD_EVEN_REL = 0.25   # ponytail: WASP-18 b measures 11 %; tighten once flatten masks transits
SECONDARY_REL = 0.10  # WASP-18 b's real secondary is 3 %


@dataclass
class Verdict:
    passed: bool
    label: str  # KNOWN / NEW / REJECTED
    reasons: list[str]

    def __str__(self):
        return f"{self.label}: " + "; ".join(self.reasons)


@lru_cache(maxsize=1)
def toi_table() -> pd.DataFrame:
    """TOI catalog, refreshed when older than a day."""
    DATA.mkdir(exist_ok=True)
    if not TOI_CSV.exists() or time.time() - TOI_CSV.stat().st_mtime > 86400:
        urllib.request.urlretrieve(TOI_URL, TOI_CSV)
    return pd.read_csv(TOI_CSV, usecols=["TIC ID", "TOI", "Period (days)", "TFOPWG Disposition"])


def _sig(a, b):
    """How many sigma apart two (value, err) pairs are."""
    return abs(a[0] - b[0]) / max((a[1] ** 2 + b[1] ** 2) ** 0.5, 1e-12)


def vet(target: str, c: Candidate) -> Verdict:
    reasons, ok = [], True
    st = c.stats
    if c.snr < SNR_FLOOR:
        ok = False; reasons.append(f"snr {c.snr:.1f} < {SNR_FLOOR}")
    else:
        reasons.append(f"snr {c.snr:.1f}")
    if c.sde < SDE_FLOOR:
        ok = False; reasons.append(f"sde {c.sde:.1f} < {SDE_FLOOR}: peak does not stand out")
    else:
        reasons.append(f"sde {c.sde:.1f}")
    if c.n_transits < MIN_TRANSITS:
        ok = False; reasons.append(f"only {c.n_transits} transit(s) with data")
    if st["harmonic_delta_log_likelihood"] > 0:
        ok = False; reasons.append("a sine fits better than a box: variable star, not a transit")
    oe = _sig(st["depth_odd"], st["depth_even"])
    oe_rel = abs(st["depth_odd"][0] - st["depth_even"][0]) / max(c.depth, 1e-12)
    if oe > SIGMA and oe_rel > ODD_EVEN_REL:
        ok = False; reasons.append(f"odd/even differ by {oe_rel:.0%} ({oe:.1f}σ): eclipsing binary at 2P?")
    else:
        reasons.append(f"odd/even agree ({oe_rel:.0%})")
    sec_depth, sec_err = st["depth_phased"]  # model shifted by half a period = secondary eclipse
    sec = sec_depth / max(sec_err, 1e-12)
    sec_rel = sec_depth / max(c.depth, 1e-12)
    if sec > SIGMA and sec_rel > SECONDARY_REL:
        ok = False; reasons.append(f"secondary eclipse {sec_rel:.0%} of primary ({sec:.1f}σ): eclipsing binary")
    else:
        reasons.append(f"secondary {sec_rel:.1%} ({sec:.1f}σ)")
    if not ok:
        return Verdict(False, "REJECTED", reasons)

    tic = int(target.upper().replace("TIC", "").strip())
    rows = toi_table().query("`TIC ID` == @tic")
    for _, r in rows.iterrows():
        p = r["Period (days)"]
        for k in (1, 2, 0.5):  # same period or a harmonic
            if p > 0 and abs(c.period - k * p) / (k * p) < 0.01:
                reasons.append(f"matches TOI {r['TOI']} (P={p:.4f}, {r['TFOPWG Disposition']})")
                return Verdict(True, "KNOWN", reasons)
    if len(rows):
        reasons.append(f"TIC has TOI(s) {', '.join(map(str, rows['TOI']))} at other periods")
    return Verdict(True, "NEW", reasons)
