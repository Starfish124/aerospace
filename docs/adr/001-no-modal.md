# ADR-001: No Modal, Mac mini only

**Decision**: every run, including whole-sector scans, runs on the Mac mini. No cloud compute.
**Why**: no real cash budget. A sector is ~20k targets at 1–3 s each; that is one night on the M4 if we stream.
**Rejected**: Modal (installed, configured, costs money per scan).
**Revisit when**: a single sector scan takes more than one night.
