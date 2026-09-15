"""The manual look: fold the light curve on the candidate period, save a PNG, and check whether
every other TESS sector of the same star shows the same period. A real planet repeats."""
import warnings

warnings.filterwarnings("ignore")
import lightkurve as lk
import matplotlib
matplotlib.use("Agg")

from transit.fetch import DATA, fetch
from transit.search import search, refine, FLATTEN_WINDOW
from transit.vet import vet


def look(target: str, sector: int | None = None) -> dict:
    """`sector` = where the candidate was found; its period seeds the multi-sector refinement."""
    result = lk.search_lightcurve(target, author="SPOC", cadence=120)
    sectors = sorted({int(s.split()[-1]) for s in result.mission})
    print(f"{target}: {len(sectors)} sectors {sectors}", flush=True)
    seed = search(fetch(target, sectors=sector or sectors[0]))[0]
    print(f"seed (sector {sector or sectors[0]}): {seed}", flush=True)
    lc_all = fetch(target)
    c = refine(lc_all, seed.period, seed.t0)
    verdict = vet(target, c)
    print(f"all sectors refined: {c}")
    print(f"verdict:             {verdict}", flush=True)
    # per-sector recovery: does each sector on its own find the same period (or a harmonic)?
    hits = []
    for s in sectors:
        try:
            cs = search(fetch(target, sectors=s), top=3)
        except Exception as e:
            print(f"  sector {s:3d}: {type(e).__name__}"); continue
        hit = next((x for x in cs if any(abs(x.period - k * c.period) / (k * c.period) < 0.01 for k in (1, 2, 0.5))), None)
        hits.append(hit is not None)
        print(f"  sector {s:3d}: {'same period, sde %.1f' % hit.sde if hit else 'not found (best ' + f'{cs[0].period:.3f} d)'}", flush=True)
    print(f"recovered in {sum(hits)}/{len(hits)} sectors")
    flat = lc_all.flatten(window_length=FLATTEN_WINDOW)
    folded = flat.fold(period=c.period, epoch_time=c.t0)
    ax = folded.scatter(s=1, alpha=0.3, label=f"P={c.period:.4f} d")
    folded.bin(time_bin_size=c.duration / 5).plot(ax=ax, color="red", lw=2, label="binned")
    ax.set_xlim(-2 * c.duration, 2 * c.duration)
    png = DATA / f"{target}_fold.png"
    ax.figure.savefig(png, dpi=110)
    print(f"fold plot:   {png}")
    return {"candidate": c, "verdict": verdict, "sectors": sectors, "recovered": sum(hits)}
