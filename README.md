# aerospace

Exoplanet transit search on public TESS data (slice A) and rocket ascent + RL lander simulation (slice B). Runs on a Mac mini.

Vocabulary: `CONTEXT.md`. Decisions: `docs/adr/`. Learning log: `docs/lessons.md`.

```
uv run aerospace lightcurve TIC100100827
uv run pytest transit/tests -q
```
