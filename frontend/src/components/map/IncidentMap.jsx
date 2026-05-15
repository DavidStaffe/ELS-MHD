import * as React from 'react';
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  useMap,
  useMapEvents,
} from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import {
  OSM_TILE_URL,
  OSM_ATTRIBUTION,
  DEFAULT_CENTER,
  DEFAULT_ZOOM,
  makeIncidentIcon,
  makeResourceIcon,
} from '@/lib/leaflet-setup';
import { fmsMeta } from '@/lib/fms-status';

/** Internal: re-centers the map when external center changes. */
function CenterUpdater({ center, zoom }) {
  const map = useMap();
  React.useEffect(() => {
    if (!center) return;
    map.setView(center, zoom ?? map.getZoom(), { animate: true });
  }, [center?.[0], center?.[1], zoom]); // eslint-disable-line
  return null;
}

/** Internal: handles map clicks (for adding/placing markers). */
function MapClickHandler({ onClick, disabled }) {
  useMapEvents({
    click(e) {
      if (disabled) return;
      onClick?.([e.latlng.lat, e.latlng.lng]);
    },
  });
  return null;
}

const RESOURCE_FALLBACK_COLOR = '#64748b';

function resourceColor(resource) {
  if (resource.fms_status !== null && resource.fms_status !== undefined) {
    const meta = fmsMeta(resource.fms_status);
    if (meta) return meta.color;
  }
  if (resource.status === 'im_einsatz') return '#eab308';
  if (resource.status === 'verfuegbar') return '#22c55e';
  if (resource.status === 'offline') return '#6b7280';
  return RESOURCE_FALLBACK_COLOR;
}

/**
 * IncidentMap – OSM-Karte fuer einen Incident.
 *
 * Props:
 *   incident: { ort_lat, ort_lng, ort_zoom }
 *   resources: [{ id, name, lat, lng, status, fms_status, kategorie }]
 *   abschnitte: [{ id, name, farbe, polygon }] (Phase 2)
 *   onMapClick(coords): user clicked on empty map
 *   onResourceMove(id, [lat,lng]): user dragged a resource pin
 *   onResourceClick(resource): user clicked a resource pin
 *   onIncidentMove([lat,lng]): user dragged the incident center pin
 *   draggableIncident: bool
 *   draggableResources: bool
 *   height: css height (default "500px")
 *   className: additional wrapper classes
 */
export function IncidentMap({
  incident,
  resources = [],
  onMapClick,
  onResourceMove,
  onResourceClick,
  onIncidentMove,
  draggableIncident = false,
  draggableResources = false,
  clickToPlace = false,
  height = '500px',
  className = '',
  showAttribution = true,
}) {
  const center = React.useMemo(() => {
    if (incident?.ort_lat != null && incident?.ort_lng != null) {
      return [incident.ort_lat, incident.ort_lng];
    }
    return DEFAULT_CENTER;
  }, [incident?.ort_lat, incident?.ort_lng]);

  const zoom = incident?.ort_zoom || (incident?.ort_lat != null ? 14 : DEFAULT_ZOOM);

  const incidentIcon = React.useMemo(() => makeIncidentIcon(), []);

  return (
    <div
      className={`els-map-wrap relative overflow-hidden rounded-md border border-border ${className}`}
      style={{ height }}
      data-testid="incident-map"
    >
      <MapContainer
        center={center}
        zoom={zoom}
        scrollWheelZoom
        className="els-map-container"
        style={{ height: '100%', width: '100%' }}
        attributionControl={showAttribution}
      >
        <TileLayer attribution={OSM_ATTRIBUTION} url={OSM_TILE_URL} />
        <CenterUpdater center={center} zoom={zoom} />
        <MapClickHandler onClick={onMapClick} disabled={!clickToPlace} />

        {incident?.ort_lat != null && incident?.ort_lng != null && (
          <Marker
            position={[incident.ort_lat, incident.ort_lng]}
            icon={incidentIcon}
            draggable={draggableIncident && !clickToPlace}
            interactive={!clickToPlace}
            eventHandlers={{
              dragend: (e) => {
                const ll = e.target.getLatLng();
                onIncidentMove?.([ll.lat, ll.lng]);
              },
            }}
          >
            <Popup>
              <div className="text-sm">
                <div className="font-semibold">{incident.name}</div>
                {incident.ort && (
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {incident.ort}
                  </div>
                )}
              </div>
            </Popup>
          </Marker>
        )}

        {resources
          .filter((r) => r.lat != null && r.lng != null)
          .map((r) => {
            const color = resourceColor(r);
            const icon = makeResourceIcon({
              label: r.name?.split(' ')[0] || '',
              color,
            });
            return (
              <Marker
                key={r.id}
                position={[r.lat, r.lng]}
                icon={icon}
                draggable={draggableResources}
                interactive={!clickToPlace}
                eventHandlers={{
                  click: () => onResourceClick?.(r),
                  dragend: (e) => {
                    const ll = e.target.getLatLng();
                    onResourceMove?.(r.id, [ll.lat, ll.lng]);
                  },
                }}
              >
                <Popup>
                  <div className="text-sm min-w-[140px]">
                    <div className="font-semibold">{r.name}</div>
                    <div className="text-xs mt-1 space-y-0.5">
                      <div className="text-muted-foreground">
                        Kategorie: <span className="text-foreground">{r.kategorie}</span>
                      </div>
                      {r.fms_status !== null && r.fms_status !== undefined ? (
                        <div className="text-muted-foreground">
                          FMS{' '}
                          <span style={{ color }} className="font-mono font-semibold">
                            {r.fms_status}
                          </span>{' '}
                          {fmsMeta(r.fms_status)?.label}
                        </div>
                      ) : (
                        <div className="text-muted-foreground">
                          Status: <span className="text-foreground">{r.status}</span>
                        </div>
                      )}
                      {r.divera_id && (
                        <div className="text-[10px] text-muted-foreground">
                          Divera: {r.divera_id}
                        </div>
                      )}
                    </div>
                  </div>
                </Popup>
              </Marker>
            );
          })}
      </MapContainer>
    </div>
  );
}
