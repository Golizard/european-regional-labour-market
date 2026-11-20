# Data provenance and storage

The project uses public Eurostat statistics, a GISCO unit index and boundary
geometries. The six small source snapshots (approximately 2.4 MB in total) are retained alongside
the analysis so the published results can be reproduced offline.

## Raw sources

| File under `raw/` | Purpose |
|---|---|
| `eurostat/unemployment_poland_2024.json` | National API/metadata example |
| `eurostat/unemployment_nuts2_2024.json` | Regional unemployment source |
| `eurostat/gdp_per_capita_pps_poland_2024.json` | National GDP/unit example |
| `eurostat/gdp_per_capita_pps_nuts2_2024.json` | Regional GDP source |
| `geography/nuts_2024_units.json` | NUTS 2024 reference codes; not boundary geometries |
| `geography/nuts_2024_level2_20m.geojson` | NUTS 2024 level-2 polygons, scale 1:20 million, EPSG:4326 |

`metadata/acquisition_manifest.json` stores exact URLs, sizes and SHA-256 hashes.
Unknown download timestamps remain `null`. A dataset's source update time is
not its observation year or download time. Future refreshes must deliberately
preserve a new snapshot and its provenance; normal notebook execution never
updates the raw files or acquisition manifest.

## Derived data

`processed/regional_labour_market_2024.csv` contains one row per EU NUTS 2 region
in 2024: 244 rows, 241 complete indicator pairs and three missing unemployment
values. Source flags are retained. See `docs/DATA_SOURCES.md` for units and definitions.

| Column | Meaning |
|---|---|
| `region_code` | Text identifier from the EU NUTS 2024 level-2 reference |
| `region_name` | Display name from the unemployment source |
| `year` | Calendar year, 2024 |
| `unemployment_pct` | Annual unemployment rate, ages 15–74, percent of the labour force |
| `unemployment_status` | Original unemployment observation flags; may be empty |
| `gdp_per_capita_pps` | GDP per inhabitant in PPS, unit `PPS_EU27_2020_HAB` |
| `gdp_status` | Original GDP observation flags; may be empty |

## Attribution and reuse

Statistical sources: Eurostat, datasets `lfst_r_lfu3rt` and `nama_10r_2gdp`.
Geographic reference: European Commission / Eurostat GISCO, NUTS 2024.
This project transforms and combines the sources; it is not an official Eurostat product.

- [Eurostat copyright and reuse policy](https://ec.europa.eu/eurostat/about-us/policies/copyright).
- [GISCO statistical-unit download provisions](https://ec.europa.eu/eurostat/web/gisco/geodata/statistical-units).

Third-party conditions are separate from any future code license. The future
boundary map must include the applicable geographic-data attribution and terms.
