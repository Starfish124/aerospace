# Run log (lab notebook)

Every command that mattered, in order, with the real output. Append-only. Read top to bottom to replay the whole thing.
Run any block yourself from `~/aerospace`.

## 2026-09-15 evening: slice A built and proven, slice B built, first candidates

### A0 bootstrap
```
uv init --python 3.12 --name aerospace
uv add lightkurve pandas pytest
uv run python -c "import lightkurve, astropy; print(lightkurve.__version__, astropy.__version__)"
→ lightkurve 2.6.0 astropy 8.0.1
gh repo create Starfish124/aerospace --public --source=. --push
```

### A1 first light curve on screen
```
uv run aerospace lightcurve TIC100100827 --sector 2      # WASP-18
target   TIC100100827
points   18299
span     27.4 days
std      2865 ppm
min dip  12451 ppm
plot     data/TIC100100827.png          ← 28 dips of ~1.1 %, visible by eye

uv run aerospace lightcurve TIC261136679 --sector 1      # Pi Mensae
points   18264   span 27.9 days   std 135 ppm   min dip 967 ppm
                                        ← the planet's dip is 226 ppm: below the noise, invisible by eye
```

### A2 blind search (truth tests)
First run: both periods correct but SNR = 0.005. Cause: BLS was not given the flux error bars, so it assumed every error = 1.0.
Fix: `BoxLeastSquares(t, f, dy=flat.flux_err.value)`.
```
uv run pytest transit/tests -q
→ 2 passed in 9.31s

uv run aerospace search TIC100100827 --sector 2
1. P=0.9414 d  depth=9474 ppm  dur=1.9 h  snr=652.4      ← WASP-18 b, published P=0.94145
2. P=1.8827 d  depth=9631 ppm  dur=1.9 h  snr=489.7      ← 2×P harmonic
3. P=2.8244 d  depth=9065 ppm  dur=1.9 h  snr=389.9      ← 3×P harmonic

uv run aerospace search TIC261136679 --sector 1
1. P=6.2665 d  depth=226 ppm  dur=2.9 h  snr=51.7        ← Pi Men c, published P=6.2678
2. P=12.5370 d  depth=227 ppm  dur=2.9 h  snr=40.8
3. P=3.1338 d  depth=126 ppm  dur=2.9 h  snr=37.9
```

### A3 vetting: the raw statistics that set the thresholds
```
TIC261136679 (Pi Men c)   depth=226
  depth           226.2 ±  4.4 ppm  ( 51.7σ)
  depth_odd       221.2 ±  6.9 ppm
  depth_even      229.5 ±  5.6 ppm
  depth_half      125.3 ±  3.3 ppm   ← NOT the secondary eclipse (astropy: model at half the period)
  depth_phased     -8.5 ±  5.0 ppm   ← this is the secondary: none, as expected for a planet
TIC100100827 (WASP-18 b)  depth=9474
  depth_odd      8901.8 ± 20.6 ppm
  depth_even     9995.1 ± 19.7 ppm   ← 11 % apart = 38σ, yet a planet → thresholds must be relative
  depth_phased    314.7 ± 14.6 ppm   ← a REAL secondary (planet's dayside), 3.3 % of primary → allow up to 10 %
```
After fixes:
```
uv run aerospace vet TIC261136679 --sector 1
KNOWN: snr 51.7; odd/even agree (4%); secondary -3.7% (-1.7σ); matches TOI 144.01 (P=6.2678, CP)
uv run aerospace vet TIC100100827 --sector 2
KNOWN: snr 652.4; odd/even agree (12%); secondary 3.3% (21.6σ); matches TOI 185.01 (P=0.9415, KP)
```

### A4 sector scan, and calibrating the vet on noise
```
uv run aerospace scan 1 --limit 40      → 54 s, 4 threads  (≈1.4 s/star → a 15,889-star sector ≈ 6–8 h)
labels: 14 NEW, 26 REJECTED             ← 35 % "new planets" is impossible; the vet was never shown noise
```
Calibration table (truth targets vs the 14 false NEW):
```
target            snr    sde  ntr   harmDLL   depth P
WASP-18b        652.4    9.3   28 -169352.6    9474 0.941
PiMen-c          51.7   10.0    5   -1331.5     226 6.267
TIC278660115     25.6    6.3   53      42.6      71 0.524   ← sine fits better than a box (harmDLL>0)
TIC114952667     12.0    5.4   54       9.3     124 0.500   ← same, at the shortest period searched
TIC355369707      7.5    3.7    3     -27.6     278 10.195
TIC234516451      8.6    5.3   13     -36.6      76 1.973
TIC55745413      11.1    5.0    2     -62.0     466 11.394  ← 2 transits
TIC302116223     19.1    3.9    3    -175.3     570 10.530
TIC38600576      11.7    6.4    1     -68.0     384 13.647  ← 1 transit
TIC382043075     29.0    7.1    2    -418.3    1856 13.895
TIC235040784     25.8    5.1    2    -327.8     962 13.928
TIC382510066      7.5    3.4    3     -27.8     285 11.496
TIC60645979       7.3    4.8    3     -26.6     486 12.502
TIC139300891     50.2    5.5   30     981.8     775 0.907   ← variable star
TIC267090033     10.6    6.0    2     -55.4    1251 13.650
TIC139250667      8.2    6.0    1     -33.7     759 13.945
```
Rules chosen from this table: SDE ≥ 8, ≥ 3 transits, harmDLL ≤ 0. Rerun:
```
uv run aerospace scan 1 --limit 40   → 40 REJECTED, 0 NEW;  uv run pytest -q → 7 passed
```

### A5 nightly job
```
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.aerospace.nightly.plist
launchctl kickstart gui/$(id -u)/com.aerospace.nightly     # started ~19:55, pid 91621
measured rate: 235 rows @20:18:33 → 249 @20:18:59 = 32 stars/min → sector 1 ≈ 8 h
```
First 885 stars of sector 1 (old vet, before the archive cross-match and radius check):
```
877 REJECTED, 2 ERROR (MAST connection drops), 3 KNOWN, 2 NEW
KNOWN  TIC231702397  P=5.0784  5472 ppm  snr  8.7  matches TOI 122.01
KNOWN  TIC234994474  P=1.4013   538 ppm  snr 16.4  matches TOI 134.01
KNOWN  TIC277683130  P=6.1962  1945 ppm  snr 40.7  matches TOI 138.01
NEW    TIC300013489  P=5.2148  3952 ppm  snr 10.2  sde 9.8    ← under the look
NEW    TIC234518605  P=5.6803 52904 ppm  snr 317   sde 8.7    ← 5.3 % deep: too deep for a planet
```

### B1 ascent (Falcon 9 from public numbers)
```
uv run python rocket/ascent.py
ideal dv per stage: [3985, 4930] total 8916 m/s
```
Pure gravity turn is knife-edge (payload 22.8 t, no fairing):
```
kick 1.5°  alt=498 km v=6771  gamma=9.3°   no orbit
kick 2.0°  alt=247 km v=7434  gamma=-1.1°  no orbit
kick 2.5°  alt= 21 km v=5991  drag 2034    no orbit   ← fell back into the air
```
With upper-stage altitude-hold:
```
payload 16.0 t kick 2.0°  t=464s alt=165 km v=7816 m/s gamma=0.4°
  ideal dv 9721  losses: gravity 1389 drag 22 steering 482  ORBIT
  bookkeeping: 9721-1389-22-482 = 7828 vs 7816 delivered → closes to 0.2 %
uv run pytest rocket -q → 3 passed
```

### B2 lander (PPO, CPU)
```
run 1  1.0M steps  0 % landings   rollout: hovers at y≈3.9 m until timeout (timeout = crash = -100 → why risk it)
run 2  0.7M steps  0 %            rollout: hovers at y≈0.7 m, x≈-2.4 (binary ±100 touchdown = a cliff)
run 3  graded touchdown reward:
  100k 0% → 200k 7% → 300k 30% → 400k 53% → 500k 97% (30 eps)   standalone 100-ep eval: 89 %
resume, 100-ep checks, keep best only:
  ... 800k 87% → 900k 93%  best 93%
uv run python rocket/train.py --eval  →  soft landings: 93% of 100 episodes
```

### Machine
```
M4, 16 GB, disk free: 4.7 GB at start → 1.8 GB (swap 14 GB, not the scan) → 6.2 GB after `uv cache prune`
data/ cache: 10–40 MB (2 MB per sector file, deleted after use)
```

### Live sky page (ADR-006), 21:30
```
uv run python - # bulk positions test: 200 TIC ids → 200 rows in 3.4 s (ra, dec, Tmag)
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.aerospace.sky.plist
:7420 was already owned by a node server + another python → moved to :7425
GET /data → http 200 in 0.04 s; rows 1459, placed 1455
screenshot: the sector-1 footprint is a curved strip of southern sky; 4 gold = known planets
  (TOI 122.01, 134.01, 138.01, 141.01 rediscovered blind), 2 red = NEW under investigation
scan rate while 3 looks + sky page compete for the CPU: 19–23 stars/min (32 alone)
```

### Sky page v2: the evidence panel, 22:00
```
scan.py now writes data/current.json for every star (flattened light curve 800 pts, BLS periodogram 500 pts,
  fold 200 bins) and keeps data/stars/<tic>.json for KNOWN/NEW. sky.py serves /current /star/<tic> /stats.
GET /current → 33.7 KB   GET /star/261136679 → KNOWN
backfill of the 6 flagged stars with the current vet:
  TIC231702397 KNOWN   ~2.7 R_earth (star 0.33 R_sun)      TOI 122.01
  TIC234994474 KNOWN   ~1.5 R_earth (star 0.60 R_sun)      TOI 134.01
  TIC277683130 KNOWN   ~5.3 R_earth (star 1.11 R_sun)      TOI 138.01
  TIC403224672 KNOWN   ~1.8 R_earth (star 1.13 R_sun)      TOI 141.01
  TIC300013489 NEW     snr 10.2 sde 9.8, 3952 ppm, no stellar radius in TIC → 33-sector look pending
  TIC234518605 REJECTED implied radius 26 R_earth → stellar companion (as predicted from 5.3 % depth)
nightly job reloaded (PYTHONUNBUFFERED), resumed: "sector 1: 1605 done, 14284 to go"
```

### The look at TIC 300013489 (the surviving NEW), 22:40
```
uv run aerospace look TIC300013489 --sector 1
33 sectors (2018 → 2025)
seed (sector 1):     P=5.2148 d  depth=3952 ppm  dur=1.9 h  snr=10.2  sde=9.8   n=6
all sectors refined: P=5.2145 d  depth=3824 ppm  dur=1.9 h  snr=47.8  sde=11.9  n=135
verdict:             NEW: snr 47.8; sde 11.9; odd/even agree (3%); secondary -1.4% (-0.7σ)
recovered in 31/32 sectors (sector 32 found 6.198 d instead; sector 89 file missing)
```
Not in TOI list, not in the NASA confirmed table. Next: who is this star (SIMBAD, TIC params, EB catalog, CTOI)?

### Who is TIC 300013489? 22:50
```
TIC: Tmag 13.28, no Teff/logg/radius in the catalog, Gaia 5280724176618264192
SIMBAD: nothing within 10 arcsec        TESS EB catalog (Prsa 2022): no match
ExoFOP community TOIs: 300013489.01  disposition PC  P=5.22 d  submitted 2022-12-09
→ KNOWN (community TOI). vet.py now checks three catalogs: NASA confirmed, TOI, CTOI.
re-vet of all NEW/ERROR rows with the full vet (scan stopped for the rewrite, then resumed):
  TIC381854774  NEW → KNOWN   ~15.9 R_earth, community TOI
  TIC229808144  NEW → KNOWN   5.3 % deep, community TOI
  TIC308452910  NEW → NEW     P=0.5315 d  2309 ppm  snr 17  sde 8.2  ~2.3 R_earth (star 0.44 R_sun)  → look running
  3 ERROR → REJECTED on retry (they were MAST connection drops)
after 3,025 stars: 12 KNOWN, 1 NEW, 0 ERROR
```

### TIC 308452910: the spinning star, 23:20
```
uv run aerospace look TIC308452910 --sector 1
25 sectors; seed P=0.5315 d depth 2309 ppm snr 17 sde 8.2
all sectors refined: P=0.5313 d depth 1911 ppm snr 71.9 sde 9.2 n=1048; secondary -5.7% (-4.0σ)
recovered in 24/24 sectors
TIC: Teff 3501 K, 0.44 R_sun M dwarf, Tmag 12.8;  SIMBAD: 2MASS J08024935-6540071 (high proper motion star)
Gaia DR3 variability: SOLAR_LIKE (rotational modulation)   TESS EB catalog: no match
→ REJECTED: brightening at phase 0.5. New vet rule; recorded in data/looks.csv (overrides scan label)
sky counts after: REJECTED 3314, KNOWN 13, NEW 1 (TIC 197570458, look running)
```

### TIC 197570458: an eclipsing binary, 23:40
```
TIC: Teff 3455 K, 0.55 R_sun, Tmag 13.1;  SIMBAD: UCAC4 260-197941 = NGTS J214358.5-380102
TESS EB catalog (Prsa 2022): MATCH   → REJECTED. vet.py now checks 4 lists: NASA confirmed, TOI, CTOI, TESS EBs.
look killed (answer known). Recorded in data/looks.csv.
```

### Sky page v3, 00:10
```
data/bright.csv: 10,145 naked-eye stars (TIC Tmag < 6.5, Dec -85..-15) fetched in 50 s → faint white background
page: full-height map, scroll zoom / drag pan / double-click reset, RA (hours) × Dec (degrees) grid,
      dashed crosshair on the star being examined, evidence panel fixed to the right column, rejection
      reasons as a list. Layout bug on first try: panel landed in the left column (no grid-column set).
```

### TIC 159693368: a hot subdwarf binary, 00:30
```
TIC: Teff 31,000 K, 0.18 R_sun, 789 pc, Tmag 15.1;  SIMBAD: EC 21101-4027 (HS* = hot subdwarf)
uv run aerospace look TIC159693368 --sector 1
6 sectors; seed P=2.0080 d depth 17509 ppm snr 12.8 sde 8.4
all sectors refined: P=2.0058 d depth 9892 ppm snr 16.3 sde 7.1 n=69
→ REJECTED by the look itself: secondary eclipse 20 % of primary (3.2σ) = eclipsing binary; recovered 4/6 sectors
vet.py now also attaches the SIMBAD name + object type to every NEW. Scan restarted with it.
Scoreboard after ~4,000 stars: 17 KNOWN, 0 NEW, 4 NEW-then-explained (CTOI, spinning star, catalogued EB, sdB binary)
```
