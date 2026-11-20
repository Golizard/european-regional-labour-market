"""Build the responsive, offline EU regional indicator map from verified files."""

from bisect import bisect_right
import hashlib
import json
import math
from pathlib import Path

from branca.element import MacroElement
import folium
import geopandas as gpd
from jinja2 import Template
import pandas as pd


EU_COUNTRIES_2024 = {
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "EL", "ES", "FI", "FR", "HR", "HU",
    "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PL", "PT", "RO", "SE", "SI", "SK",
}
MISSING_COLOR = "#aab5bd"
GDP_COLORS = ["#dfebf2", "#b4cedf", "#7baac6", "#407e9f", "#1b4d6b"]
UNEMPLOYMENT_COLORS = ["#f8e8dd", "#efc7ad", "#dfa07b", "#c47154", "#974a39"]


def load_map_data(project_root):
    """Verify source geometry and select the same NUTS geography as the analysis."""
    manifest = json.loads((project_root / "data/metadata/acquisition_manifest.json").read_text(encoding="utf-8"))
    records = {record["path"]: record for record in manifest["files"]}
    if len(records) != len(manifest["files"]):
        raise ValueError("Duplicate source paths in the manifest.")

    def verified_source(relative_path):
        record = records[relative_path]
        path = project_root / relative_path
        content = path.read_bytes()
        if len(content) != record["size_bytes"] or hashlib.sha256(content).hexdigest() != record["sha256"]:
            raise ValueError(f"Source checksum mismatch: {relative_path}")
        return path

    reference_path = verified_source("data/raw/geography/nuts_2024_units.json")
    reference_units = json.loads(reference_path.read_text(encoding="utf-8"))
    reference_codes = {code for code in reference_units if len(code) == 4 and code[:2] in EU_COUNTRIES_2024}
    analysis = pd.read_csv(
        project_root / "data/processed/regional_labour_market_2024.csv",
        dtype={"region_code": "string", "unemployment_status": "string", "gdp_status": "string"},
    )
    if analysis.duplicated(["region_code", "year"]).any():
        raise ValueError("Duplicate analytical region-year keys.")
    if set(analysis["region_code"]) != reference_codes or set(analysis["year"]) != {2024}:
        raise ValueError("The analytical table does not match the selected NUTS 2024 scope.")
    for column in ("gdp_per_capita_pps", "unemployment_pct"):
        if not analysis[column].dropna().map(math.isfinite).all():
            raise ValueError(f"Non-finite indicator values: {column}")
    if not analysis["unemployment_pct"].dropna().between(0, 100).all():
        raise ValueError("Unemployment values outside 0–100 percent.")
    if not analysis["gdp_per_capita_pps"].dropna().gt(0).all():
        raise ValueError("Non-positive GDP values.")

    boundaries_path = verified_source("data/raw/geography/nuts_2024_level2_20m.geojson")
    boundaries = gpd.read_file(boundaries_path)
    if not {"NUTS_ID", "LEVL_CODE", "CNTR_CODE", "NAME_ENGL", "geometry"}.issubset(boundaries.columns):
        raise ValueError("Unexpected boundary schema.")
    if boundaries.crs is None or not boundaries["LEVL_CODE"].eq(2).all():
        raise ValueError("Missing CRS or incorrect NUTS level.")
    boundaries = boundaries.to_crs(epsg=4326)
    selected = boundaries.loc[
        boundaries["NUTS_ID"].isin(reference_codes),
        ["NUTS_ID", "CNTR_CODE", "NAME_ENGL", "geometry"],
    ].rename(columns={
        "NUTS_ID": "region_code", "CNTR_CODE": "country_code", "NAME_ENGL": "country_name",
    })
    if set(selected["region_code"]) != reference_codes:
        raise ValueError("Missing reference-region geometries.")
    if not selected["country_code"].eq(selected["region_code"].str[:2]).all():
        raise ValueError("Country codes do not match region-code prefixes.")
    if selected["country_name"].isna().any() or selected["country_name"].str.strip().eq("").any():
        raise ValueError("Missing country names in boundary data.")
    geometry = selected.geometry
    if geometry.isna().any() or geometry.is_empty.any() or not geometry.is_valid.all():
        raise ValueError("Missing, empty or invalid region geometry.")
    map_data = selected.merge(analysis, on="region_code", how="left", validate="one_to_one")
    context = boundaries.loc[~boundaries["NUTS_ID"].isin(reference_codes), ["geometry"]].copy()
    return map_data, context


def make_metric(frame, column, flag_column, title, unit, colors, digits):
    """Use unrounded quintile boundaries for both styling and the legend."""
    values = frame[column].dropna()
    edges = values.quantile([0, 0.2, 0.4, 0.6, 0.8, 1]).drop_duplicates().tolist()
    if len(edges) < 2:
        raise ValueError(f"Insufficient variation for a color scale: {column}")
    if len(edges) - 1 != len(colors):
        # Quantile ties may reduce the class count. Keep distinct palette endpoints.
        count = len(edges) - 1
        colors = [colors[round(index * (len(colors) - 1) / max(count - 1, 1))] for index in range(count)]
    return {
        "column": column, "flagColumn": flag_column, "title": title, "unit": unit,
        "edges": edges, "colors": colors, "digits": digits,
        "available": int(values.count()), "missing": int(frame[column].isna().sum()),
    }


def metric_color(value, metric):
    """Assign lower-inclusive classes; include the maximum in the final class."""
    if value is None or pd.isna(value):
        return MISSING_COLOR
    index = min(max(bisect_right(metric["edges"], value) - 1, 0), len(metric["colors"]) - 1)
    return metric["colors"][index]


def build_map(project_root, map_data, context):
    """Render one data layer with responsive controls and a synchronized legend."""
    assets = project_root / "map_assets"
    metrics = {
        "gdp": make_metric(map_data, "gdp_per_capita_pps", "gdp_status", "GDP per capita", "PPS per inhabitant", GDP_COLORS, 0),
        "unemployment": make_metric(map_data, "unemployment_pct", "unemployment_status", "Unemployment", "% of the labour force, ages 15–74", UNEMPLOYMENT_COLORS, 1),
    }
    west, south, east, north = map_data.total_bounds
    config = {
        "totalRegions": len(map_data),
        "totalCountries": int(map_data["region_code"].str[:2].nunique()),
        "metrics": metrics, "missingColor": MISSING_COLOR,
        "europeBounds": [[34, -13], [71, 34]],
        "allBounds": [[float(south), float(west)], [float(north), float(east)]],
    }
    map_object = folium.Map(
        location=[52, 12], zoom_start=4, tiles=None, control_scale=False,
        zoom_control="bottomright", attribution_control=True, prefer_canvas=False,
    )
    # Only Leaflet is needed. Local pinned assets avoid unused Bootstrap/jQuery
    # global styles and allow the saved page to work without internet access.
    map_object.default_js = [("leaflet", "assets/vendor/leaflet-1.9.4.js")]
    map_object.default_css = [("leaflet_css", "assets/vendor/leaflet-1.9.4.css")]
    folium.map.CustomPane("context", z_index=200, pointer_events=False).add_to(map_object)
    if not context.empty:
        folium.GeoJson(
            json.loads(context.to_json(drop_id=True)), pane="context",
            style_function=lambda feature: {"fillColor": "#e5ebef", "fillOpacity": 0.8, "color": "#ffffff", "weight": 0.5},
            control=False, interactive=False,
        ).add_to(map_object)
    regions = folium.GeoJson(
        json.loads(map_data.to_json(drop_id=True)), name="EU regions", control=False,
        style_function=lambda feature: {
            "fillColor": metric_color(feature["properties"]["gdp_per_capita_pps"], metrics["gdp"]),
            "fillOpacity": 0.95, "color": "#ffffff", "weight": 0.65,
            "className": "atlas-region",
        },
    ).add_to(map_object)
    panel = MacroElement()
    panel.regions = regions
    panel.config = config
    panel.styles = (assets / "style.css").read_text(encoding="utf-8")
    panel.layout = (assets / "layout.html").read_text(encoding="utf-8")
    panel.interactions = (assets / "interactions.js").read_text(encoding="utf-8")
    panel._template = Template("""
{% macro header(this, kwargs) %}
<title>EU Labour Market — Regional Explorer, 2024</title>
<meta name="description" content="Explore GDP per capita and unemployment across 244 EU NUTS 2 regions in 2024. Eurostat data, verified geography and observation flags.">
<meta name="theme-color" content="#182c3b">
<link rel="icon" href="data:,">
<style>{{ this.styles | safe }}</style>
{% endmacro %}
{% macro html(this, kwargs) %}{{ this.layout | safe }}{% endmacro %}
{% macro script(this, kwargs) %}
(function () {
    const map = {{ this._parent.get_name() }};
    const regions = {{ this.regions.get_name() }};
    const config = {{ this.config | tojson }};
    {{ this.interactions | safe }}
})();
{% endmacro %}
""")
    panel.add_to(map_object)
    return map_object, config


def save_map(project_root, map_object):
    """Write the static page while retaining local relative Leaflet assets."""
    output = project_root / "docs/index.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    html = map_object.get_root().render()
    # Permit browser page zoom; Folium's default viewport disables it.
    html = html.replace("initial-scale=1.0, maximum-scale=1.0, user-scalable=no", "initial-scale=1.0")
    html = html.replace("<html>", '<html lang="en">', 1)
    output.write_text(html, encoding="utf-8")
    return output


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    frame, surrounding = load_map_data(root)
    generated_map, configuration = build_map(root, frame, surrounding)
    output_path = save_map(root, generated_map)
    print(f"Saved {output_path.relative_to(root)}: {len(frame)} regions, {output_path.stat().st_size / 1_000_000:.2f} MB")
