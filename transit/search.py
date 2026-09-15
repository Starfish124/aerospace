"""Light curve -> candidates. Detrend, then BLS (ADR-004)."""
from dataclasses import dataclass

import numpy as np
from astropy.timeseries import BoxLeastSquares

MIN_PERIOD, MAX_PERIOD = 0.5, 30.0  # days
DURATIONS = np.array([0.04, 0.08, 0.12, 0.17, 0.25])  # days; 1 h .. 6 h
FLATTEN_WINDOW = 721  # cadences of 2 min = 1 day; longer than any transit we care about


@dataclass
class Candidate:
    period: float
    t0: float
    duration: float
    depth: float  # fractional, e.g. 0.01 = 1 %
    snr: float

    def __str__(self):
        return f"P={self.period:.4f} d  depth={self.depth*1e6:.0f} ppm  dur={self.duration*24:.1f} h  snr={self.snr:.1f}"


def search(lc, top=3) -> list[Candidate]:
    """Return the `top` strongest distinct periodic dips, strongest first."""
    flat = lc.flatten(window_length=FLATTEN_WINDOW).remove_outliers(sigma_upper=4, sigma_lower=20)
    t, f = flat.time.value, flat.flux.value
    span = t.max() - t.min()
    bls = BoxLeastSquares(t, f, dy=flat.flux_err.value)
    periods = bls.autoperiod(DURATIONS, minimum_period=MIN_PERIOD, maximum_period=min(MAX_PERIOD, span / 2),
                             frequency_factor=1.0)
    res = bls.power(periods, DURATIONS, objective="snr")
    order = np.argsort(res.power)[::-1]
    out = []
    for i in order:
        p = res.period[i]
        if any(abs(p - c.period) / c.period < 0.02 for c in out):
            continue  # same peak, neighbouring grid point
        stats = bls.compute_stats(p, res.duration[i], res.transit_time[i])
        out.append(Candidate(float(p), float(res.transit_time[i]), float(res.duration[i]),
                             float(res.depth[i]), float(stats["depth"][0] / stats["depth"][1])))
        if len(out) == top:
            break
    return out
