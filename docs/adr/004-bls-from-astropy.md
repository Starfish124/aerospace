# ADR-004: Transit search uses astropy's BoxLeastSquares

**Decision**: `astropy.timeseries.BoxLeastSquares`, no custom search.
**Why**: standard, tested, one import.
**Revisit when**: the hard truth test (Pi Mensae c, ~300 ppm) fails. Next option is Transit Least Squares (TLS).
