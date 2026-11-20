# Data Sources

## Regional unemployment rate

- Provider: Eurostat.
- Dataset code: `lfst_r_lfu3rt`.
- Dataset title: Unemployment rates by educational attainment level
  and NUTS 2 region.
- Underlying source: European Union Labour Force Survey (EU-LFS).
- Frequency: Annual.
- Unit: Percentage of the labour force.
- Selected age group: 15–74 years.
- Selected sex category: Total.
- Selected education category: All ISCED 2011 levels.
- Reference year: 2024.

### Definition

The unemployment rate is the number of unemployed persons divided
by the labour force, multiplied by 100.

The labour force consists of employed and unemployed persons.

Unemployed persons are not employed during the reference week,
are available for work within the following two weeks, and have
actively sought work during the four-week period ending with the
reference week, or have found a job starting within three months.

Registration at an employment office is not required.

### Sources

- https://ec.europa.eu/eurostat/cache/metadata/en/reg_lmk_esms.htm
- https://ec.europa.eu/eurostat/statistics-explained/index.php?title=Glossary:Unemployment

### Verification status

National and regional responses have been preserved and verified against
the manifest. The regional slice uses `freq=A`, `isced11=TOTAL`, `sex=T`,
`age=Y15-74`, `unit=PC`, `time=2024` and `geoLevel=nuts2`.
The NUTS 2024 reference codes and EU scope have been verified below.

## Verified geographic scope

- Reference geography: NUTS 2024, level 2, EU-27 countries.
- Reference source:
  https://gisco-services.ec.europa.eu/distribution/v2/nuts/nuts-2024-units.json
- Expected regions in the reference: 244.
- Matched unique region codes: 244.
- Available unemployment values for 2024: 241.
- Missing unemployment values: 3.

The missing values concern:

- DEB2 — Trier;
- PL43 — Lubuskie;
- FI20 — Åland.

All three missing observations carry the `u` flag (low reliability).
Missing values are preserved and are not replaced with zero.

Twelve additional geographic categories returned by the statistical
API were excluded because their codes do not belong to the selected
NUTS 2024 reference geography.

Geographic coverage is complete, but unemployment value coverage is incomplete.
All 244 regions remain in the analysis table. Correlations use the 241 complete
pairs. A sensitivity analysis excludes available unemployment observations
whose flags contain `u`, leaving 222 complete pairs. GDP flags `p` and `e`
are retained in both variants.

## Regional GDP per capita

- Provider: Eurostat.
- Dataset code: `nama_10r_2gdp`.
- Dataset title: Gross domestic product (GDP) at current market
  prices by NUTS 2 region.
- Frequency: Annual.
- Selected unit: `PPS_EU27_2020_HAB`.
- Unit label: Purchasing power standard (PPS, EU27 from 2020),
  per inhabitant.
- Reference year: 2024.
- Metadata:
  https://ec.europa.eu/eurostat/cache/metadata/en/reg_eco10_esms.htm

### Interpretation and limitations

Regional GDP measures economic activity within a region.
GDP per capita divides regional GDP by its population.
It does not measure residents' average wages or disposable income.

Conversion to PPS uses national purchasing power parities (PPP).
The same PPP is applied to every region within a country
for a given year. Regional price-level differences within
the country are therefore not separately accounted for.

### Verification status

National and regional responses confirm the selected unit. The national
example carries the `p` flag, meaning provisional. The regional request uses
`freq=A`, `unit=PPS_EU27_2020_HAB`, `time=2024` and `geoLevel=nuts2`.

All 244 reference regions have a matching GDP record and an available value.
GDP flags: 142 provisional (`p`), 33 estimated (`e`) and 69 without an attached
flag. No flag does not guarantee an absence of limitations.

## Observation flags and comparability

| Flag | Meaning | Treatment |
|---|---|---|
| `u` | Low reliability | Preserve; compare the main result with an exclusion variant |
| `b` | Break in time series | Preserve; a warning for temporal comparisons |
| `d` | Definition differs; see metadata | Preserve; document unresolved comparability limits |
| `p` | Provisional | Preserve |
| `e` | Estimated | Preserve |

Combined flags retain all meanings, for example `bdu`. Filtering for `u`
therefore checks containment, not equality. A missing flag is not a missing
indicator value. Reasons behind national `b`/`d` flags have not yet been
fully reviewed; the analysis does not claim complete methodological comparability.

- Flag legend: https://ec.europa.eu/eurostat/data/database
- Acquisition URLs, source update times and checksums:
  `data/metadata/acquisition_manifest.json`.
- Source definitions and the analysis report are separate from acquisition dates.

## Map boundaries

- Source: European Commission / Eurostat GISCO, NUTS 2024.
- Original file: `NUTS_RG_20M_2024_4326_LEVL_2.geojson`.
- URL: https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/NUTS_RG_20M_2024_4326_LEVL_2.geojson
- Level: NUTS 2; cartographic scale: 1:20 million; CRS: EPSG:4326.
- Original geometries: 299. Selected EU reference geometries: 244.
- Selected missing, empty and invalid geometries: zero.
- Join: exact `NUTS_ID` / `region_code`, validated one-to-one.
- Country labels in tooltips and region details use GISCO `NAME_ENGL`, with
  `CNTR_CODE` checked against the region-code prefix.

The 244 study regions remain present when an indicator is unavailable. The map
shows missing unemployment values in grey. Other available GISCO regions are
pale geographic context and do not enter the analysis. The initial view focuses
on continental Europe; the all-regions view includes the EU's outermost regions.

Each indicator has its own quintile-based color classes calculated from available
regional values. Original numeric class boundaries determine color membership.
The legend and active geometry styles use the same thresholds. Observation
flags appear in region details; the map does not suppress `u`, `p` or `e` values.

Geographic attribution displayed on the map:
© EuroGeographics for the administrative boundaries.
