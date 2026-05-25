/**
 * Geocoding via Nominatim (OSM).
 * Fair-Use: max 1 req/s pro Quelle, User-Agent muss gesetzt sein (Browser
 * setzt automatisch). Wir limitieren clientseitig via Debounce.
 */
const NOMINATIM = 'https://nominatim.openstreetmap.org';

export async function searchAddress(query, { limit = 5, language = 'de' } = {}) {
  if (!query || query.trim().length < 3) return [];
  const params = new URLSearchParams({
    q: query.trim(),
    format: 'jsonv2',
    limit: String(limit),
    'accept-language': language,
    addressdetails: '1',
  });
  const url = `${NOMINATIM}/search?${params}`;
  const res = await fetch(url, {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) throw new Error('Geocoding fehlgeschlagen');
  const data = await res.json();
  return data.map((item) => ({
    label: item.display_name,
    lat: parseFloat(item.lat),
    lng: parseFloat(item.lon),
    type: item.type,
    importance: item.importance,
    address: item.address || {},
  }));
}

export async function reverseGeocode(lat, lng, { language = 'de' } = {}) {
  const params = new URLSearchParams({
    lat: String(lat),
    lon: String(lng),
    format: 'jsonv2',
    'accept-language': language,
    addressdetails: '1',
    zoom: '16',
  });
  const url = `${NOMINATIM}/reverse?${params}`;
  const res = await fetch(url, {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) return null;
  const data = await res.json();
  return data?.display_name || null;
}
