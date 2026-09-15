# ADR-002: No language model in the pipeline or the nightly run

**Decision**: the pipeline is plain Python. The nightly launchd job is plain Python. Claude builds and explains; it never judges a light curve.
**Why**: a small statistical test beats a language model at reading dips. Headless Claude also loads the global CLAUDE.md and hooks into every run.
**Rejected**: LLM vetting of candidates; `claude -p` summarizing reports.
