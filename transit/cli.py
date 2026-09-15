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


def cmd_report(a):
    from transit.report import report
    print(report())


def cmd_nightly(a):
    from transit.report import nightly
    nightly()


def cmd_ascent(a):
    from dataclasses import replace
    from rocket.ascent import FALCON9, fly
    v = replace(FALCON9, payload=a.payload)
    dv = v.ideal_dv()
    print("ideal dv per stage: " + "  ".join(f"{d:.0f}" for d in dv) + f"  total {sum(dv):.0f} m/s")
    f = fly(v, kick_deg=a.kick)
    print(f)
    for row in f.log[::6]:
        print("  t=%4ds  alt=%4d km  v=%5d m/s" % row)


def cmd_look(a):
    from transit.look import look
    look(a.target, a.sector)


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
    sub.add_parser("report", help="summarise all scans into reports/<date>.txt").set_defaults(fn=cmd_report)
    sub.add_parser("nightly", help="scan the next sector, write and commit the report").set_defaults(fn=cmd_nightly)
    s = sub.add_parser("ascent", help="fly a Falcon 9-class rocket to orbit, print the delta-v budget")
    s.add_argument("--payload", type=float, default=16_000)
    s.add_argument("--kick", type=float, default=2.0)
    s.set_defaults(fn=cmd_ascent)
    s = sub.add_parser("look", help="manual look: fold on the candidate period, check every sector, save PNG")
    s.add_argument("target")
    s.add_argument("--sector", type=int, default=None, help="sector the candidate was found in")
    s.set_defaults(fn=cmd_look)
    a = p.parse_args()
    a.fn(a)
