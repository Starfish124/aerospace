# Lessons

One entry per milestone. What we did, why, and what surprised us. Read this when you want to understand the code, not just run it.

## A1–A2: light curve on screen, blind search passes both truth tests (2026-09-15)

**What we did.** `fetch.py` downloads TESS 2-minute SPOC light curves through `lightkurve` and stitches sectors. `search.py` flattens the curve (1-day window) and runs BLS over periods 0.5–14 days. Two truth tests, no period hint: WASP-18 b (P 0.9415 d) and Pi Mensae c (P 6.268 d). Both recovered on the first sector we tried.

**Numbers.** WASP-18 b: depth 9500 ppm, SNR 652. Pi Men c: depth 226 ppm, SNR 52. One sector = 2 MB on disk, 18k points, and the whole search takes ~4 s per target on the M4.

**Why BLS.** A transit is a box: flat, dip, flat. Box Least Squares slides a box of every trial period, phase and duration over the data and asks "how much better does a box fit than no box". It is the standard first-pass search behind most TESS discoveries. It is in astropy, so we wrote zero search code (ADR-004).

**What SNR means here.** Depth divided by its uncertainty. SNR 7 is the usual floor: below that, noise alone produces such dips too often. Pi Men c at 52 is comfortably real; the reason it is "hard" is the depth (226 ppm) against per-point noise of 135 ppm, so any single dip is invisible by eye and only folding on the right period reveals it.

**What surprised us.**
- The first run reported SNR 0.005 for a planet that was plainly there. BLS was never given the flux error bars, so it assumed every error was 1.0. Lesson: a statistic with the wrong error model is silently wrong, not loudly wrong.
- The search returns harmonics as candidates 2 and 3 (2P, 3P, P/2). Same planet, wrong fold. Vetting must collapse those before anything is called "new".
- Flattening with a window shorter than the transit eats the transit. 1 day is long enough for every planet we care about and short enough to remove the star's own wobble.
