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

## A3: vetting and the TOI catalog (2026-09-15)

**What we did.** `vet.py` takes the strongest candidate and runs three kill-checks, then asks the TOI catalog (TESS Objects of Interest, 8k rows, refreshed daily from ExoFOP) whether that star already has a candidate at that period or a harmonic of it. Verdict: KNOWN, NEW or REJECTED, always with the reasons.

**The three checks.** (1) SNR ≥ 7. (2) Odd and even transits have the same depth: an eclipsing binary found at half its true period shows two different dips alternating. (3) No secondary eclipse at phase 0.5 deeper than 10 % of the primary: two stars eclipse each other twice per orbit, a planet only once (its own eclipse is tiny).

**What surprised us.**
- Astropy's `depth_half` is not the secondary eclipse. It is the depth of a model at half the period. The secondary is `depth_phased`. Reading the docstring before trusting a field name saved a false pipeline.
- Sigma alone is the wrong threshold at high SNR. WASP-18 b's odd/even depths differ by 11 %, which is 38σ because the error bars are tiny. A 3σ rule rejected the most obvious planet in the sky. The fix is a relative threshold on top of sigma: reject only when the difference is both significant and large.
- WASP-18 b has a real secondary eclipse of 315 ppm (the planet's own dayside going behind the star), 21σ. A planet can have a secondary; a binary has a big one. Same lesson: relative, not absolute.
- The 11 % odd/even wobble itself is our detrending distorting a 0.94-day planet. Noted in code as a `ponytail:` ceiling; masking transits before flattening is the upgrade.

## A4: scanning a whole sector on the mini (2026-09-15)

**What we did.** `scan.py` reads MAST's own bulk-download script for a sector (15,889 targets for sector 1), then for each star: download the 2 MB file, search, vet, write one CSV row, delete the file. Four threads. Resumable: rerunning skips stars already in the CSV. Measured: 40 stars in 54 s, so a sector is ~6 hours. Disk stays at a few MB.

**What surprised us.**
- The first sample called 14 of 40 stars NEW. Real rate for planets is under 1 %. The vetting from A3 was calibrated on two bright planets and never on noise. Lesson: a filter is only calibrated once it has seen what it must reject.
- Three standard checks fixed it, and the numbers separated cleanly. SDE (how far the best peak stands above the rest of the periodogram): real planets 9.3 and 10.0, every false positive under 7.2. Transit count: seven of the fourteen had one or two dips, which is a glitch, not a period. Sine-vs-box: astropy reports whether a sinusoid fits better than a box; variable stars pulsing every half day were being called planets at exactly the shortest period we search.
- BLS "SNR" alone is misleading on noisy stars: it will always find *some* box. SDE asks the better question: is this box special compared with every other box it tried.
