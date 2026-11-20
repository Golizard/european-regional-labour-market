"""Verify snapshots, offline notebook execution and reproducible artifacts."""

import argparse
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pandas as pd


NOTEBOOKS = ("01_api_and_metadata.ipynb", "02_exploratory_analysis.ipynb", "03_interactive_map.ipynb")
ARTIFACTS = (
    "data/processed/regional_labour_market_2024.csv",
    "reports/tables/data_quality_summary.csv",
    "reports/tables/descriptive_statistics.csv",
    "reports/tables/correlation_summary.csv",
)


def verify_sources(root):
    """Check manifest integrity and source-query agreement without network access."""
    manifest = json.loads((root / "data/metadata/acquisition_manifest.json").read_text())
    paths = [record["path"] for record in manifest["files"]]
    if len(paths) != len(set(paths)):
        raise AssertionError("Duplicate manifest paths.")
    actual_paths = {p.relative_to(root).as_posix() for p in (root / "data/raw").rglob("*") if p.is_file()}
    if set(paths) != actual_paths:
        raise AssertionError("Raw files and manifest paths do not match.")
    for record in manifest["files"]:
        path = (root / record["path"]).resolve()
        if not path.is_relative_to((root / "data/raw").resolve()):
            raise AssertionError("Source path escapes data/raw.")
        content = path.read_bytes()
        if len(content) != record["size_bytes"] or hashlib.sha256(content).hexdigest() != record["sha256"]:
            raise AssertionError(f"Source integrity failure: {record['path']}")
        payload = json.loads(content)
        query = parse_qs(urlparse(record["source_url"]).query)
        if "dimension" in payload:
            dataset_id = payload["extension"]["id"].lower()
            if urlparse(record["source_url"]).path.rsplit("/", 1)[-1].lower() != dataset_id:
                raise AssertionError("Dataset identifier does not match the source URL.")
            for dimension_code in payload["id"]:
                if dimension_code in query:
                    selected_codes = set(payload["dimension"][dimension_code]["category"]["index"])
                    if selected_codes != set(query[dimension_code]):
                        raise AssertionError(f"Source filter mismatch: {dimension_code}")
            if record.get("source_updated_at") != payload["updated"]:
                raise AssertionError("Source update metadata mismatch.")
        started = record.get("request_started_at_utc")
        received = record.get("downloaded_at_utc")
        if started and received and datetime.fromisoformat(started) > datetime.fromisoformat(received):
            raise AssertionError("Response received before request start.")
    print(f"PASS: {len(paths)} source snapshots match the manifest and query filters.")


def expect_value_error(operation, label):
    try:
        operation()
    except ValueError:
        return
    raise AssertionError(f"Missing validation: {label}")


def check_parser(namespace):
    """Exercise position mapping, missing data and unsupported input rejection."""
    parser = namespace["regional_table"]
    payload = {
        "class": "dataset", "extension": {"id": "TEST"},
        "id": ["geo", "time", "unit"], "size": [3, 1, 1],
        "dimension": {
            "geo": {"category": {"index": {"AA02": 1, "AA01": 0, "AA03": 2},
                                 "label": {"AA01": "First", "AA02": "Second", "AA03": "Third"}}},
            "time": {"category": {"index": {"2024": 0}}},
            "unit": {"category": {"index": {"PC": 0}}},
        },
        "value": {"1": 20, "0": 10}, "status": {"2": "u"},
    }

    def parse(value):
        return parser(value, "test", {"time": "2024", "unit": "PC"}, "value", "status")

    frame = parse(payload).set_index("region_code")
    if frame.loc["AA01", "value"] != 10 or frame.loc["AA02", "value"] != 20:
        raise AssertionError("JSON-stat positions mapped incorrectly.")
    if not pd.isna(frame.loc["AA03", "value"]) or frame.loc["AA03", "status"] != "u":
        raise AssertionError("Missing position or its flag was lost.")
    dense = copy.deepcopy(payload)
    dense["value"] = [10, 20, None]
    pd.testing.assert_frame_equal(parse(payload), parse(dense))
    for field in ("time", "unit"):
        invalid = copy.deepcopy(payload)
        invalid["dimension"][field]["category"]["index"] = {"WRONG": 0}
        expect_value_error(lambda: parse(invalid), f"wrong {field}")
    invalid = copy.deepcopy(payload)
    invalid["size"][1] = 2
    expect_value_error(lambda: parse(invalid), "varying non-geographic dimension")
    invalid = copy.deepcopy(payload)
    invalid["dimension"]["geo"]["category"]["index"]["AA02"] = 0
    expect_value_error(lambda: parse(invalid), "duplicate positions")


def check_correlations(namespace):
    """Check average tied ranks and prevent pairwise deletion or constant inputs."""
    summarize = namespace["summarize_correlations"]
    tied = pd.DataFrame({"gdp_per_capita_pps": [10, 20, 20, 40], "unemployment_pct": [4, 2, 2, 1]})
    result = summarize(tied, "test")
    if abs(result["spearman_rho"] + 1) > 1e-12 or result["n_regions"] != 4:
        raise AssertionError("Spearman calculation with ties is incorrect.")
    incomplete = tied.copy()
    incomplete.loc[0, "unemployment_pct"] = float("nan")
    expect_value_error(lambda: summarize(incomplete, "test"), "incomplete pairs")
    constant = tied.copy()
    constant["gdp_per_capita_pps"] = 10
    expect_value_error(lambda: summarize(constant, "test"), "constant indicator")


def execute_notebook(path):
    """Execute Python cells in a fresh namespace; reject network operations."""
    import matplotlib.pyplot as plt
    import requests

    notebook = json.loads(path.read_text(encoding="utf-8"))
    namespace = {"__name__": "__main__", "__file__": str(path)}
    log = io.StringIO()
    original_directory = Path.cwd()
    try:
        os.chdir(path.parent)
        with contextlib.redirect_stdout(log), patch.object(
            requests.sessions.Session, "request",
            side_effect=AssertionError("Network request attempted during offline verification."),
        ), patch("socket.create_connection", side_effect=AssertionError("Network connection attempted.")), patch.object(plt, "show"):
            for index, cell in enumerate(notebook["cells"]):
                if cell["cell_type"] != "code":
                    continue
                source = cell["source"]
                if isinstance(source, list):
                    source = "".join(source)
                exec(compile(source, f"{path.name}:cell-{index}", "exec"), namespace)
            if "regional_table" in namespace:
                check_parser(namespace)
            if "summarize_correlations" in namespace:
                check_correlations(namespace)
            if "map_config" in namespace:
                config = namespace["map_config"]
                frame = namespace["gdf_map"]
                if config["totalRegions"] != len(frame):
                    raise AssertionError("Map configuration loses regions.")
                for metric in config["metrics"].values():
                    values = frame[metric["column"]]
                    if metric["available"] != values.notna().sum() or metric["missing"] != values.isna().sum():
                        raise AssertionError("Map indicator coverage is incorrect.")
                    if metric["edges"][0] != values.min() or metric["edges"][-1] != values.max():
                        raise AssertionError("Map scale does not cover the indicator range.")
    except Exception:
        print(log.getvalue())
        raise
    finally:
        os.chdir(original_directory)
    print(f"PASS: {path.name} executes offline in a fresh process; validation cases pass.")


def read_artifact(path):
    return pd.read_csv(path)


def verify_project(root):
    verify_sources(root)
    baseline = {name: read_artifact(root / name) for name in ARTIFACTS}
    with tempfile.TemporaryDirectory(prefix="eurostat-verify-") as temporary:
        workspace = Path(temporary) / "project"
        shutil.copytree(root, workspace, ignore=shutil.ignore_patterns(".venv", ".git", "__pycache__", ".ipynb_checkpoints"))
        raw_before = {p: p.read_bytes() for p in (workspace / "data/raw").rglob("*") if p.is_file()}
        manifest_before = (workspace / "data/metadata/acquisition_manifest.json").read_bytes()
        # Remove derived artifacts so execution cannot accidentally reuse stale outputs.
        shutil.rmtree(workspace / "data/processed")
        shutil.rmtree(workspace / "reports/tables")
        shutil.rmtree(workspace / "reports/figures")
        (workspace / "docs/index.html").unlink(missing_ok=True)
        environment = os.environ.copy()
        environment.update(MPLBACKEND="Agg", MPLCONFIGDIR=str(Path(temporary) / "matplotlib"), PYTHONDONTWRITEBYTECODE="1")
        for name in NOTEBOOKS:
            subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--execute-notebook", str(workspace / "notebooks" / name)],
                env=environment, check=True,
            )
        for name in ARTIFACTS:
            pd.testing.assert_frame_equal(
                baseline[name], read_artifact(workspace / name),
                check_exact=False, rtol=1e-12, atol=1e-12,
            )
        for name in ("indicator_distributions.png", "gdp_unemployment_scatter.png"):
            if not (workspace / "reports/figures" / name).read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
                raise AssertionError(f"Invalid generated figure: {name}")
        html = (workspace / "docs/index.html").read_text(encoding="utf-8")
        for marker in ('id="atlas-app"', 'window.labourAtlas', 'assets/vendor/leaflet-1.9.4.js', 'assets/vendor/leaflet-1.9.4.css'):
            if html.count(marker) != 1:
                raise AssertionError(f"Missing or duplicate map structure: {marker}")
        for name in ("leaflet-1.9.4.js", "leaflet-1.9.4.css", "LEAFLET-LICENSE.txt"):
            if not (workspace / "docs/assets/vendor" / name).is_file():
                raise AssertionError(f"Missing local map dependency: {name}")
        if any(path.read_bytes() != content for path, content in raw_before.items()):
            raise AssertionError("Notebook execution changed a raw source.")
        if (workspace / "data/metadata/acquisition_manifest.json").read_bytes() != manifest_before:
            raise AssertionError("Notebook execution changed acquisition metadata.")
    print("PASS: all four CSV artifacts reproduce; both PNG figures and map HTML regenerate.")
    print("PASS: raw snapshots and acquisition metadata remain unchanged.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-notebook", type=Path, help=argparse.SUPPRESS)
    arguments = parser.parse_args()
    if arguments.execute_notebook:
        execute_notebook(arguments.execute_notebook.resolve())
    else:
        verify_project(Path(__file__).resolve().parents[1])
