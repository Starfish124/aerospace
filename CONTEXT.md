# CONTEXT

Vocabulary for this repo. Use these words in code, docs and conversation. A new concept goes here before it goes into code.

## Slice A: transit (exoplanets)

- **Target**: one star, identified by its TIC id (TESS Input Catalog number), e.g. `TIC100100827`.
- **Light curve**: brightness of a target over time, from TESS 2-minute cadence SPOC files.
- **Detrend**: remove the star's slow brightness wobble so only dips remain (`lightkurve.flatten`).
- **Transit search**: find periodic box-shaped dips. Algorithm: BLS (Box Least Squares, `astropy.timeseries.BoxLeastSquares`).
- **Candidate**: a (period, depth, duration, SNR) the search returned above threshold.
- **Vetting**: checks that kill false positives: odd/even depth match, no secondary eclipse, SNR floor.
- **Known**: the target already has a TOI (TESS Object of Interest) or confirmed planet at that period. **New**: it does not.
- **Truth test**: run the search blind on a target with a confirmed planet; pass = the known period is recovered.
- **Sector scan**: run fetch → search → vet on every 2-minute target in one TESS sector, streaming one file at a time.
- **Report**: plain-text summary of a scan: counts, top candidates, New vs Known.

## Slice B: rocket

- **Ascent**: 1D staged climb computed from the rocket equation plus gravity and drag losses.
- **Lander**: 2D gymnasium environment; an RL agent learns to land softly on a pad.

## Decisions

See `docs/adr/`. Read them before proposing Modal, an LLM in the loop, a custom search algorithm, or a UI.
