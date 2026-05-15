/**
 * Leaflet icon fix + shared map constants.
 * Leaflet's default marker icons reference relative URLs that break with
 * webpack/CRA. We point to a stable CDN.
 */
import L from 'leaflet';

// Patch default icon paths once.
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl:
    'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

export const OSM_TILE_URL =
  'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
export const OSM_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';

export const DEFAULT_CENTER = [51.1657, 10.4515]; // Germany centroid
export const DEFAULT_ZOOM = 6;

/** Custom DivIcon for resources, colored by FMS status. */
export function makeResourceIcon({ label = '', color = '#22c55e' } = {}) {
  const safeLabel = String(label).slice(0, 4);
  const html = `
    <div class="els-resource-pin" style="--pin-color:${color}">
      <span class="els-resource-pin-label">${safeLabel}</span>
    </div>
  `;
  return L.divIcon({
    html,
    className: 'els-resource-pin-wrap',
    iconSize: [40, 40],
    iconAnchor: [20, 38],
    popupAnchor: [0, -34],
  });
}

/** Custom DivIcon for the incident center. */
export function makeIncidentIcon() {
  const html = `
    <div class="els-incident-pin">
      <div class="els-incident-pin-inner"></div>
    </div>
  `;
  return L.divIcon({
    html,
    className: 'els-incident-pin-wrap',
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
}
