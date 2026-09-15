# ADR-006: One live sky page (amends ADR-005)

**Decision**: a single self-contained page on :7425 shows the sector's patch of sky with every scanned star lighting up as it is processed, coloured by verdict. Stdlib HTTP server, one HTML string, no framework.
**Why**: Sarvesh wants to watch the pipeline look at stars, not only read CSV rows. ADR-005's "terminal only" stands for everything else; this is the one exception.
**Rejected**: a dashboard framework, a web UI for candidates, a 3D star field. Positions come from the TIC catalog in bulk (200 stars in 3.4 s), so the page also works for rows scanned before it existed.
