# Local map dependencies

Leaflet 1.9.4 is retained locally so `docs/index.html` works without a network
connection and without unused global Bootstrap or jQuery styles.

- JavaScript: https://unpkg.com/leaflet@1.9.4/dist/leaflet.js
- Stylesheet: https://unpkg.com/leaflet@1.9.4/dist/leaflet.css
- License: https://unpkg.com/leaflet@1.9.4/LICENSE

The original license is included as `LEAFLET-LICENSE.txt`. No marker images or
layer-switch images are used by this map. Keep this directory beside the HTML
when opening or publishing the page. These library assets are not statistical
source snapshots and are not part of the data acquisition manifest.
