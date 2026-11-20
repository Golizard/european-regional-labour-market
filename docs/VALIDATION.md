# Project validation

## Offline reproduction

From the project root, using the project environment:

```bash
python scripts/verify_project.py
python -m pip check
```

The verifier checks all six preserved sources against the acquisition manifest,
including file sizes, SHA-256 checksums and statistical API filters. It runs all
three notebooks in separate Python processes in a temporary project copy with
network requests blocked and derived artifacts removed first.

All four CSV artifacts must reproduce to numerical tolerance. Both scientific
figures and the map HTML must regenerate. Raw snapshots and acquisition metadata
must remain unchanged. The dependency check detects incompatible installed
package requirements; it does not test installation in a fresh environment.

## Data checks

- JSON-stat dimensions, selected categories and geographic positions are checked
  before conversion. Validation cases include sparse and dense values,
  out-of-order mappings, missing observations, flags and invalid filters.
- Region-year keys must be unique and match the EU NUTS 2024 reference geography.
- Joins are validated one-to-one; numeric values must be finite, unemployment
  must lie between 0 and 100, and available GDP values must be positive.
- All 244 regions remain in the analysis table. Correlations use 241 complete
  pairs; excluding unemployment flags containing `u` leaves 222 pairs.
- Correlation validation covers tied ranks, incomplete pairs and constant inputs.
- Map geometries must have a declared CRS and be present, non-empty and valid.
  Country-code prefixes and country-name completeness are checked.

## Browser checks

Optional interface checks are implemented in `scripts/check_map.cjs`. They require
Node.js, Playwright and its Chromium browser, independently of the Python workflow.
With those dependencies available, run:

```bash
node scripts/check_map.cjs
```

The checks cover six viewport sizes: 1440×900, 1024×768, 820×1180, 390×844,
320×568 and 844×390. They exercise indicator switching, synchronized legends,
missing-value styling, flags, country labels, touch and keyboard selection,
responsive resizing, geographic extents and direct `file://` opening.
They also check for browser errors, external requests and panel overlap.

## Limits

Passing these checks establishes consistency with the preserved source snapshots,
not the absence of source-data or methodological limitations. It does not test
a fresh-data acquisition workflow or establish causal relationships.
Chromium viewport and touch emulation does not constitute physical-device or
Safari certification. See `DATA_SOURCES.md` and `../reports/report.md` for
definitions, observation flags and analytical limitations.
