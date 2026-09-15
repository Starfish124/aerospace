# aerospace

Exoplanet transit search on public TESS data, plus a rocket ascent simulator and a reinforcement-learning lander. Runs on one Mac mini, no cloud.

Vocabulary: `CONTEXT.md`. Decisions: `docs/adr/`. Learning log, one entry per milestone: `docs/lessons.md`.

## Results so far (2026-09-15)

| What | Result |
|---|---|
| Blind recovery of WASP-18 b (TIC 100100827) | P = 0.9414 d, depth 9474 ppm, SNR 652 |
| Blind recovery of Pi Mensae c (TIC 261136679) | P = 6.2665 d, depth 226 ppm, SNR 52 |
| Vetting on 40 random sector-1 stars | 0 false NEW (was 14 before SDE / transit-count / sine-vs-box rules) |
| Falcon 9 ascent from public numbers | ideal 8916 m/s; flown: orbit at 16 t, losses gravity 1389 / drag 22 / steering 482 m/s |
| PPO lander | 93 % soft landings over 100 episodes, ~3 min CPU training |

A NEW candidate is one that passes vetting and is in neither the TOI catalog nor the NASA Exoplanet Archive. None yet; sector 1 is being scanned nightly.

## Commands

```
uv run pytest -q                                  # 13 tests, incl. both truth tests
uv run aerospace lightcurve TIC100100827          # download + describe + PNG
uv run aerospace search TIC261136679 --sector 1   # blind BLS search, top 3
uv run aerospace vet TIC261136679                 # KNOWN / NEW / REJECTED with reasons
uv run aerospace look TIC261136679                # manual look: fold + every-sector check + PNG
uv run aerospace scan 1 --limit 200               # stream-scan a sector (resumable)
uv run aerospace report                           # reports/<date>.txt
uv run aerospace ascent --payload 16000 --kick 2  # fly a Falcon 9 to orbit
uv run python rocket/train.py                     # train the lander (CPU)
uv run python rocket/train.py --eval              # 100-episode landing rate + ASCII landing
```

Nightly: `launchd` job `com.aerospace.nightly` runs `aerospace nightly` at 01:00: scans the lowest incomplete sector, writes and commits the report. No language model anywhere in the loop (ADR-002).
