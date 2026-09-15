"""aerospace <command> <target>. Terminal only (ADR-005)."""
import argparse
import numpy as np


def cmd_lightcurve(a):
    from transit.fetch import fetch, DATA
    lc = fetch(a.target, a.sector)
    flux = lc.flux.value
    print(f"target   {a.target}")
    print(f"points   {len(lc)}")
    print(f"span     {lc.time.value.max() - lc.time.value.min():.1f} days")
    print(f"std      {np.std(flux) * 1e6:.0f} ppm")
    print(f"min dip  {(1 - flux.min()) * 1e6:.0f} ppm")
    png = DATA / f"{a.target}.png"
    lc.plot().figure.savefig(png, dpi=100)
    print(f"plot     {png}")


def cmd_search(a):
    from transit.fetch import fetch
    from transit.search import search
    for i, c in enumerate(search(fetch(a.target, a.sector)), 1):
        print(f"{i}. {c}")


def cmd_vet(a):
    from transit.fetch import fetch
    from transit.search import search
    from transit.vet import vet
    c = search(fetch(a.target, a.sector))[0]
    print(c)
    print(vet(a.target, c))


def cmd_scan(a):
    from transit.scan import scan
    print("wrote", scan(a.sector, a.limit, a.workers))


def main():
    p = argparse.ArgumentParser(prog="aerospace")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("lightcurve", help="download and describe a target's light curve")
    s.add_argument("target")
    s.add_argument("--sector", type=int, default=None)
    s.set_defaults(fn=cmd_lightcurve)
    s = sub.add_parser("search", help="blind transit search, top 3 candidates")
    s.add_argument("target")
    s.add_argument("--sector", type=int, default=None)
    s.set_defaults(fn=cmd_search)
    s = sub.add_parser("vet", help="vet the strongest candidate and check the TOI catalog")
    s.add_argument("target")
    s.add_argument("--sector", type=int, default=None)
    s.set_defaults(fn=cmd_vet)
    s = sub.add_parser("scan", help="scan every 2-min target in a sector, streaming")
    s.add_argument("sector", type=int)
    s.add_argument("--limit", type=int, default=None)
    s.add_argument("--workers", type=int, default=4)
    s.set_defaults(fn=cmd_scan)
    a = p.parse_args()
    a.fn(a)
