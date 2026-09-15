"""Truth tests: blind recovery of confirmed planets. No period hint is given to the search.
Needs network the first time (fetch caches under data/)."""
import pytest
from transit.fetch import fetch
from transit.search import search

CASES = [
    # target, sector, known period (days), how hard
    ("TIC100100827", 2, 0.9415, "WASP-18 b, ~1% deep"),
    ("TIC261136679", 1, 6.268, "Pi Mensae c, ~300 ppm deep"),
]


@pytest.mark.parametrize("target,sector,period,label", CASES)
def test_blind_recovery(target, sector, period, label):
    lc = fetch(target, sectors=sector)
    cands = search(lc)
    best = cands[0]
    assert abs(best.period - period) / period < 0.01, f"{label}: got {best.period:.4f}, want {period}"
    assert best.snr > 7, f"{label}: snr {best.snr:.1f}"
