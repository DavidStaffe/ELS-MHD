import * as React from 'react';
import {
  MapContainer,
  TileLayer,
  Marker,
  useMap,
  useMapEvents,
} from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { searchAddress, reverseGeocode } from '@/lib/geocode';
import {
  OSM_TILE_URL,
  OSM_ATTRIBUTION,
  DEFAULT_CENTER,
  DEFAULT_ZOOM,
  makeIncidentIcon,
} from '@/lib/leaflet-setup';
import { MapPin, Search, Loader2, Crosshair } from 'lucide-react';

function FlyTo({ center, zoom }) {
  const map = useMap();
  React.useEffect(() => {
    if (center) map.flyTo(center, zoom ?? 15, { duration: 0.6 });
  }, [center?.[0], center?.[1]]); // eslint-disable-line
  return null;
}

function ClickToSet({ onClick }) {
  useMapEvents({
    click(e) {
      onClick?.([e.latlng.lat, e.latlng.lng]);
    },
  });
  return null;
}

/**
 * MapPicker – kleine Karte mit Adress-Suche + Klick-/Drag-Pin.
 *
 * Props:
 *   value: { lat, lng } | null – aktuelle Auswahl
 *   onChange({ lat, lng, address }): bei Klick/Drag/Search ausgeloest
 *   height: css height (default "240px")
 *   addressQuery: optionaler externer Suchbegriff (zB die Eingabe im Adressfeld)
 *   onAddressResolved(address): wenn Suche eine Adresse zurueckliefert
 */
export function MapPicker({
  value,
  onChange,
  height = '240px',
  className = '',
}) {
  const [query, setQuery] = React.useState('');
  const [results, setResults] = React.useState([]);
  const [loading, setLoading] = React.useState(false);
  const [open, setOpen] = React.useState(false);

  const debouncedSearch = React.useRef(null);

  const center = React.useMemo(() => {
    if (value?.lat != null && value?.lng != null) {
      return [value.lat, value.lng];
    }
    return DEFAULT_CENTER;
  }, [value?.lat, value?.lng]);

  const zoom = value?.lat != null ? 15 : DEFAULT_ZOOM;
  const icon = React.useMemo(() => makeIncidentIcon(), []);

  const handleSearch = React.useCallback(async (q) => {
    if (!q || q.trim().length < 3) {
      setResults([]);
      return;
    }
    setLoading(true);
    try {
      const items = await searchAddress(q);
      setResults(items);
      setOpen(items.length > 0);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const onQueryChange = (e) => {
    const v = e.target.value;
    setQuery(v);
    if (debouncedSearch.current) clearTimeout(debouncedSearch.current);
    debouncedSearch.current = setTimeout(() => handleSearch(v), 450);
  };

  const pickResult = (item) => {
    setOpen(false);
    setQuery(item.label);
    onChange?.({
      lat: item.lat,
      lng: item.lng,
      address: item.label,
    });
  };

  const handleMapClick = async ([lat, lng]) => {
    onChange?.({ lat, lng, address: null });
    // Reverse-geocode in background (non-blocking)
    try {
      const addr = await reverseGeocode(lat, lng);
      if (addr) {
        onChange?.({ lat, lng, address: addr });
      }
    } catch {
      /* ignore */
    }
  };

  const handleMarkerDrag = async (e) => {
    const ll = e.target.getLatLng();
    handleMapClick([ll.lat, ll.lng]);
  };

  return (
    <div className={`space-y-2 ${className}`} data-testid="map-picker">
      <Popover open={open && results.length > 0} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="search"
              value={query}
              onChange={onQueryChange}
              placeholder="Adresse oder Ort suchen…"
              className="h-9 pl-8 pr-8"
              data-testid="map-picker-search"
            />
            {loading && (
              <Loader2 className="absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 animate-spin text-muted-foreground" />
            )}
          </div>
        </PopoverTrigger>
        <PopoverContent
          className="w-[var(--radix-popover-trigger-width)] p-0 bg-card border-border"
          align="start"
          onOpenAutoFocus={(e) => e.preventDefault()}
        >
          <ul className="max-h-60 overflow-y-auto" data-testid="map-picker-results">
            {results.map((r, i) => (
              <li key={`${r.lat},${r.lng},${i}`}>
                <button
                  type="button"
                  onClick={() => pickResult(r)}
                  className="w-full text-left px-3 py-2 hover:bg-surface-raised text-sm els-focus-ring"
                  data-testid={`map-picker-result-${i}`}
                >
                  <div className="flex items-start gap-2">
                    <MapPin className="h-3.5 w-3.5 shrink-0 mt-0.5 text-primary" />
                    <span className="line-clamp-2">{r.label}</span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </PopoverContent>
      </Popover>

      <div
        className="relative overflow-hidden rounded-md border border-border bg-surface-sunken"
        style={{ height }}
      >
        <MapContainer
          center={center}
          zoom={zoom}
          scrollWheelZoom
          style={{ height: '100%', width: '100%' }}
        >
          <TileLayer attribution={OSM_ATTRIBUTION} url={OSM_TILE_URL} />
          <FlyTo center={value?.lat != null ? [value.lat, value.lng] : null} zoom={zoom} />
          <ClickToSet onClick={handleMapClick} />
          {value?.lat != null && value?.lng != null && (
            <Marker
              position={[value.lat, value.lng]}
              icon={icon}
              draggable
              eventHandlers={{ dragend: handleMarkerDrag }}
            />
          )}
        </MapContainer>
        {value?.lat == null && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-background/40 text-caption text-muted-foreground">
            <Crosshair className="h-3.5 w-3.5 mr-1" />
            Klicke auf die Karte oder suche eine Adresse
          </div>
        )}
      </div>
      {value?.lat != null && (
        <div className="flex items-center justify-between gap-2 text-caption text-muted-foreground">
          <span className="font-mono tabular-nums" data-testid="map-picker-coords">
            {value.lat.toFixed(5)}, {value.lng.toFixed(5)}
          </span>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-6 px-2"
            onClick={() => onChange?.(null)}
            data-testid="map-picker-clear"
          >
            entfernen
          </Button>
        </div>
      )}
    </div>
  );
}
