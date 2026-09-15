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

## B1: ascent calculator (2026-09-15)

**What we did.** `rocket/ascent.py` holds a Falcon 9 built from public numbers (two stages: dry mass, propellant, thrust, Isp). Two things come out. The **ideal delta-v** from the rocket equation, 8916 m/s for the 22.8 t payload. And a **flown** ascent: 2D, round Earth, exponential atmosphere, 0.1 s steps. Stage 1 does a gravity turn after one small pitch kick; stage 2 holds a climb rate toward 200 km and cuts off at circular speed. `uv run aerospace ascent --payload 16000 --kick 2`.

**The rocket equation in one line.** delta-v = Isp × g0 × ln(full mass / empty mass). Fuel buys speed logarithmically: doubling the fuel does not double the speed. That log is the wall ADR-003 talks about; no fuel choice removes it, a better Isp only shifts it.

**Where the speed goes.** Orbit needs ~7800 m/s. The flight delivers 9721 m/s of ideal thrust and loses 1389 to gravity (thrusting upward while gravity pulls down), 22 to drag (surprisingly small: the rocket is out of thick air in a minute) and 482 to steering (the controller pitching off the velocity vector). What is left, 7816, matches the burnout speed to 1 %: the bookkeeping closes, so the sim is not hiding energy.

**What surprised us.**
- A pure gravity turn is knife-edge: kick 2.0° almost orbits, 2.5° falls back into the atmosphere. That is why every real upper stage steers closed-loop. Ten lines of altitude-hold made insertion robust.
- Drag is nearly irrelevant to the budget; gravity loss is 60× bigger. Rockets go up first to escape drag, then sideways to escape gravity loss.
- We make orbit with 16 t, SpaceX advertises 22.8 t. The gap is our crude steering (482 m/s wasted) and no fairing separation. Marked as the `ponytail:` ceiling: a real guidance law is the upgrade.

## B2: a lander that learned to land (2026-09-15)

**What we did.** `rocket/lander_env.py` is a 2D lander with readable physics (moon gravity, one main engine, two side thrusters, fuel). `rocket/train.py` trains PPO from stable-baselines3 on the CPU: 8 parallel copies of the world, 100k steps every ~8 s. Result: **93 % soft landings over 100 fresh episodes**, in about 1.4 M steps total (~3 minutes of compute). `uv run python rocket/train.py --eval` replays one landing as ASCII.

**What reinforcement learning is, in one line.** The agent tries things, gets a number back (the reward), and shifts toward whatever raised the number. We never wrote a landing rule; we wrote the scoreboard.

**What surprised us: three runs, three ways the scoreboard lied.**
1. *Run 1, 0 %: it learned to hover.* Timeout and crash both cost 100 points, and descending the last 4 m paid about 4 points. A rational agent hovers until the clock runs out. Fix: no penalty for timing out, 10× stronger reward for getting closer, and a small cost for every step alive.
2. *Run 2, 0 %: it hovered 0.7 m above the pad.* Touchdown was a binary +100 or −100, and it sat just outside the 2 m pad tolerance. A cliff makes a cautious agent freeze. Fix: grade the touchdown (speed, angle, distance each cost points), so a near miss still pays.
3. *Run 3, 97 % then 89 %:* the 30-episode checkpoint flattered it, and PPO wobbles from one checkpoint to the next. Fix: judge on 100 episodes and keep only the best checkpoint. Best-of-run reached 93 %.

**The lesson that transfers.** Every bug was in the reward, not the physics or the algorithm. Designing the scoreboard is the whole job; the learning itself is a library call.

## The sky page, and a memory lesson (2026-09-15, late)

**What we did.** ADR-006: one live page on :7425. The scan now writes what it sees for every star (light curve, periodogram, fold) and the page draws it as it happens; known and new stars keep their evidence so you can click them. Stars are placed from the TIC catalog in bulk, 200 positions in 3.4 s.

**What surprised us.**
- Three "look at every sector" jobs ran at once and the machine killed all three for memory. The BLS period grid gets denser with the square of the time span: one sector is 27 days, thirty-three sectors is three years, so the grid grew by a factor of ~10,000. Fix: on long baselines only refine in a ±1 % window around the period one sector already found. Same physics, a thousandth of the memory.
- The pipeline's own throughput was being halved by those looks. When they died the scan doubled its rate. Contention is invisible until you measure the rate.
- Port 7420 was already taken by another project's server; the sky page silently answered 404s from a stranger. Always `lsof` a port before trusting a 200 or a 404 from it.

## The first "NEW" candidate, and the third catalog (2026-09-15, 23:00)

**What happened.** TIC 300013489 passed every check: same 5.2145-day period in 31 of 32 sectors over seven years, 135 transits, SNR 48, flat odd/even, no secondary. Not in the TOI list, not in the NASA confirmed table. For twenty minutes it was a discovery.

**What it was.** A Community TOI: CTOI 300013489.01, a planet candidate a citizen scientist submitted to ExoFOP in December 2022. There are three lists, not two: confirmed planets (NASA), TESS's own candidates (TOI), and candidates anyone can submit (CTOI). We checked two.

**What it still means.** The pipeline found, on its own and blind, a real planet candidate that took a human years to flag. That is the proof the method works. It also shows the honest size of the opportunity: sector 1 has had eight years of eyes on it. Anything "new" there must clear three catalogs, and even then the first suspicion should be a fourth list we have not heard of.

**The habit to keep.** Before calling anything new, go looking for the reason it is not. The moment of "wait, why has nobody seen this" is a prompt to search harder, not to celebrate.

**Scoreboard after 3,025 stars.** 12 known planets or candidates rediscovered blind (TOI 122, 134, 138, 141 and eight more, sizes from 1.5 to 16 Earth radii), 1 stellar companion rejected by its implied 26 Earth-radius size, 1 NEW left under the look (TIC 308452910, a 0.53-day signal around a small red star).

## The second survivor was a spinning star (2026-09-15, 23:30)

**What happened.** TIC 308452910: same 0.5313-day dip in 24 of 24 sectors, 1,048 transits, SNR 72, no catalog match. A 2-Earth-radius world on a 13-hour orbit around a small red star would be a real find.

**What it was.** A spotted star rotating every 13 hours. Gaia DR3 lists it as a "solar-like" variable. The fold shows a broad, rounded dimming with no flat bottom, and the star is *brighter* at phase 0.5 at 4σ. A transit can only remove light; it can never add light half an orbit later. A star spot going round the back does exactly that.

**The rule that was missing.** A significant brightening at phase 0.5 now rejects. Two other habits came out of it: every NEW gets its Gaia variability class attached, and a full multi-sector look now writes its own verdict (`data/looks.csv`) that outranks the single-sector scan on the sky page and in the report. In one sector the brightening was only 1.6σ; it took 24 sectors to see it at 4σ. More data does not just confirm, it also kills.

**Scoreboard after 3,305 stars.** 13 KNOWN rediscovered blind, 2 false NEW killed by the look (a community TOI, a spinning star), 1 NEW under the look (TIC 197570458: 7.6-day, 4.9 % deep, ~13 R_earth around a 0.55 R_sun star).

## Four candidates, four explanations (2026-09-16, 00:30)

TIC 159693368 was the fourth NEW of the night: a 2-day, 1.75 % dip that would be a 2.6-Earth-radius planet if the star were normal. The star is a hot subdwarf, the exposed helium core of a star that lost its envelope, 31,000 K and a fifth the size of the Sun. With six sectors instead of one the look saw a secondary eclipse a fifth as deep as the primary: two stars, not a planet.

**Pattern of the night.** Every one of the four survivors was real, periodic, and physical. None was a planet nobody knew about. The order in which they died: catalog (CTOI), more data (rotation seen at 4σ only after 24 sectors), catalog (TESS EB list), more data (secondary seen only with 6 sectors). The vet now asks four lists, Gaia, and SIMBAD before it says NEW, and a look outranks the scan. Tomorrow's NEW, if any, will have survived all of that.
