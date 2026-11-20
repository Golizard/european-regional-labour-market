// The renderer supplies the Leaflet map, region layer and verified configuration.
const byId = (id) => document.getElementById(id);
const mobileLayout = window.matchMedia("(max-width: 720px)");
let activeMetric = "gdp";
let selectedLayer = null;

byId("atlas-map-slot").appendChild(map.getContainer());
byId("atlas-total-regions").textContent = `${config.totalRegions} EU regions`;
byId("atlas-scope").textContent = `${config.totalRegions} regions in ${config.totalCountries} EU countries, 2024.`;

function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (character) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[character]);
}

function formatNumber(value, digits = 0) {
    return new Intl.NumberFormat("en-GB", {
        minimumFractionDigits: digits, maximumFractionDigits: digits,
    }).format(value);
}

function formatValue(value, metricKey, withUnit = true) {
    if (value === null || !Number.isFinite(value)) return "Not available";
    if (metricKey === "gdp") return `${formatNumber(value)}${withUnit ? " PPS" : ""}`;
    return `${formatNumber(value, 1)}%`;
}

function flagDescription(flags) {
    const meanings = {u: "low reliability", b: "time-series break", d: "different definition", p: "provisional", e: "estimated"};
    return [...(flags || "")].map((flag) => meanings[flag] || flag).join(", ");
}

function regionColor(properties) {
    const metric = config.metrics[activeMetric];
    const value = properties[metric.column];
    if (value === null || !Number.isFinite(value)) return config.missingColor;
    let index = 0;
    while (index < metric.colors.length - 1 && value >= metric.edges[index + 1]) index += 1;
    return metric.colors[index];
}

function regionStyle(layer, hovered = false) {
    const selected = layer === selectedLayer;
    return {
        fillColor: regionColor(layer.feature.properties),
        fillOpacity: hovered || selected ? 1 : 0.95,
        color: selected || hovered ? "#153b53" : "#ffffff",
        weight: selected ? 2 : hovered ? 1.6 : 0.65,
        opacity: 1,
    };
}

function tooltipContent(properties) {
    const metric = config.metrics[activeMetric];
    const flags = properties[metric.flagColumn];
    const note = flags ? `<small>${escapeHtml(flagDescription(flags))} (${escapeHtml(flags)})</small>` : "";
    return `<strong>${escapeHtml(properties.region_name)}</strong><small>${escapeHtml(properties.country_name)}</small><span class="atlas-tooltip-value">${formatValue(properties[metric.column], activeMetric)}</span><small>${escapeHtml(metric.title)} · ${escapeHtml(properties.region_code)}</small>${note}`;
}

function updateLegend() {
    const metric = config.metrics[activeMetric];
    byId("atlas-metric-title").textContent = metric.title;
    byId("atlas-metric-unit").textContent = metric.unit;
    byId("atlas-coverage").textContent = `${metric.available} / ${config.totalRegions}`;
    byId("atlas-coverage").title = "Regions with available values";
    byId("atlas-coverage").setAttribute("aria-label", `${metric.available} of ${config.totalRegions} regions have available values`);
    byId("atlas-color-strip").innerHTML = metric.colors.map((color) => `<span style="background:${color}"></span>`).join("");
    byId("atlas-range-min").textContent = formatNumber(metric.edges[0], metric.digits);
    byId("atlas-range-max").textContent = formatNumber(metric.edges.at(-1), metric.digits);
    byId("atlas-legend-rows").innerHTML = metric.colors.map((color, index) => {
        const upper = `${index === metric.colors.length - 1 ? "" : "< "}${formatNumber(metric.edges[index + 1], metric.digits)}`;
        return `<div class="atlas-legend-row"><span class="atlas-swatch" style="background:${color}"></span><span>${formatNumber(metric.edges[index], metric.digits)} – ${upper.replace("<", "&lt;")}</span></div>`;
    }).join("");
    byId("atlas-class-note").textContent = `${metric.colors.length} quantile classes · equal-weight regions. The maximum is included in the last class.`;
    byId("atlas-missing-key").hidden = metric.missing === 0;
    byId("atlas-missing-text").textContent = `Not available · ${metric.missing} regions`;
}

function selectMetric(metricKey) {
    if (!Object.hasOwn(config.metrics, metricKey)) return;
    activeMetric = metricKey;
    document.querySelectorAll("[data-metric]").forEach((button) => {
        button.setAttribute("aria-pressed", String(button.dataset.metric === metricKey));
    });
    regions.eachLayer((layer) => {
        layer.setStyle(regionStyle(layer));
        layer.setTooltipContent(tooltipContent(layer.feature.properties));
    });
    updateLegend();
}

function selectRegion(layer) {
    const previous = selectedLayer;
    selectedLayer = layer;
    if (previous) previous.setStyle(regionStyle(previous));
    if (!layer) {
        byId("atlas-region-content").hidden = true;
        byId("atlas-region-empty").hidden = false;
        byId("atlas-region-card").classList.remove("has-selection");
        byId("atlas-bottom").classList.remove("has-selection");
        return;
    }
    layer.closeTooltip();
    layer.setStyle(regionStyle(layer));
    layer.bringToFront();
    const properties = layer.feature.properties;
    byId("atlas-region-code").textContent = `${properties.country_name} · ${properties.region_code} · 2024`;
    byId("atlas-region-name").textContent = properties.region_name;
    byId("atlas-region-gdp").textContent = formatValue(properties.gdp_per_capita_pps, "gdp", false);
    byId("atlas-region-unemployment").textContent = formatValue(properties.unemployment_pct, "unemployment");
    byId("atlas-region-gdp").classList.toggle("is-missing", properties.gdp_per_capita_pps === null);
    byId("atlas-region-unemployment").classList.toggle("is-missing", properties.unemployment_pct === null);
    const notes = [];
    if (properties.gdp_status) notes.push(`GDP: ${flagDescription(properties.gdp_status)} (${properties.gdp_status}).`);
    if (properties.unemployment_status) notes.push(`Unemployment: ${flagDescription(properties.unemployment_status)} (${properties.unemployment_status}).`);
    byId("atlas-region-flags").textContent = notes.join(" ") || "No observation flags attached; see data limitations below.";
    byId("atlas-region-empty").hidden = true;
    byId("atlas-region-content").hidden = false;
    byId("atlas-region-card").classList.add("has-selection");
    byId("atlas-bottom").classList.add("has-selection");
    if (mobileLayout.matches) {
        requestAnimationFrame(() => {
            const tray = byId("atlas-bottom");
            tray.scrollTop = 0;
        });
    }
}

regions.eachLayer((layer) => {
    layer.bindTooltip(tooltipContent(layer.feature.properties), {
        className: "atlas-tooltip", sticky: true, opacity: 1, direction: "auto", offset: [12, 0],
    });
    layer.on("mouseover", () => layer.setStyle(regionStyle(layer, true)));
    layer.on("mouseout", () => layer.setStyle(regionStyle(layer)));
    layer.on("click", () => selectRegion(layer));
    const element = layer.getElement();
    if (element) {
        element.setAttribute("tabindex", "0");
        element.setAttribute("role", "button");
        element.setAttribute("aria-label", `Explore ${layer.feature.properties.region_name}`);
        element.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                selectRegion(layer);
            }
        });
    }
});

document.querySelectorAll("[data-metric]").forEach((button) => {
    button.addEventListener("click", () => selectMetric(button.dataset.metric));
});
byId("atlas-clear-region").addEventListener("click", () => selectRegion(null));

function setExtent(extent) {
    const bounds = extent === "europe" ? config.europeBounds : config.allBounds;
    map.fitBounds(bounds, {padding: [22, 26], animate: false});
    byId("atlas-view-europe").setAttribute("aria-pressed", String(extent === "europe"));
    byId("atlas-view-all").setAttribute("aria-pressed", String(extent === "all"));
}

byId("atlas-view-europe").addEventListener("click", () => setExtent("europe"));
byId("atlas-view-all").addEventListener("click", () => setExtent("all"));
byId("atlas-key").open = !mobileLayout.matches;
mobileLayout.addEventListener("change", (event) => {
    byId("atlas-key").open = !event.matches;
});

const resizeObserver = new ResizeObserver(() => {
    requestAnimationFrame(() => map.invalidateSize({pan: false}));
});
resizeObserver.observe(byId("atlas-map-stage"));
selectMetric("gdp");
map.invalidateSize({pan: false});
setExtent("europe");

// Stable handles allow browser checks without relying on generated Folium IDs.
window.labourAtlas = Object.freeze({
    map, regions, selectMetric,
    selectRegion: (code) => selectRegion(regions.getLayers().find((layer) => layer.feature.properties.region_code === code) || null),
    getState: () => ({activeMetric, selectedRegion: selectedLayer?.feature.properties.region_code || null}),
});
