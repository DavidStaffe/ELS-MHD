import * as React from 'react';
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  Polygon,
  Tooltip,
  useMap,
  useMapEvents,
} from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import '@geoman-io/leaflet-geoman-free';
import '@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css';
import {
  OSM_TILE_URL,
  OSM_ATTRIBUTION,
  DEFAULT_CENTER,
  DEFAULT_ZOOM,
  makeIncidentIcon,
  makeResourceIcon,
} from '@/lib/leaflet-setup';
import { fmsMeta } from '@/lib/fms-status';
import { getFarbe } from '@/lib/abschnitt-meta';

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

/**
 * Internal: Geoman drawing/edit controller.
 * Props:
 *   mode: null | "draw" | "edit"
 *   color: hex string used for drawing
 *   onDrawComplete(latlngs): polygon drawn, returns [[lat,lng]...]
 *   onCancel(): user cancels drawing
 */
function GeomanController({ mode, color, onDrawComplete, onCancel }) {
  const map = useMap();

  React.useEffect(() => {
    if (!map?.pm) return;
    // Disable any active mode first
    map.pm.disableDraw();
    map.pm.disableGlobalEditMode();
    map.pm.disableGlobalRemovalMode();

    if (mode === 'draw') {
      map.pm.setPathOptions({
        color,
        fillColor: color,
        fillOpacity: 0.2,
        weight: 2,
      });
      map.pm.enableDraw('Polygon', {
        snappable: true,
        finishOn: 'dblclick',
        allowSelfIntersection: false,
      });
    }
  }, [mode, color, map]);

  React.useEffect(() => {
    if (!map?.pm) return;
    const handler = (e) => {
      const layer = e.layer;
      const latlngs = layer.getLatLngs()[0].map((p) => [p.lat, p.lng]);
      // Remove the drawn ghost layer; we re-render via state.
      try { map.removeLayer(layer); } catch { /* noop */ }
      onDrawComplete?.(latlngs);
    };
    map.on('pm:create', handler);
    return () => map.off('pm:create', handler);
  }, [map, onDrawComplete]);

  // Escape key cancels
  React.useEffect(() => {
    if (mode !== 'draw') return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') {
        map.pm.disableDraw();
        onCancel?.();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [mode, map, onCancel]);

  return null;
}

/**
 * Internal: editable polygon. Renders a react-leaflet <Polygon>, and when
 * `editable=true` enables Geoman edit on the underlying layer (vertex drag,
 * delete vertex on right-click etc.). Emits onChange(latlngs) after edit.
 */
function EditablePolygon({ abschnitt, editable, onClick, onChange }) {
  const ref = React.useRef(null);
  const farbe = getFarbe(abschnitt.farbe);

  React.useEffect(() => {
    const layer = ref.current;
    if (!layer || !layer.pm) return undefined;
    if (editable) {
      layer.pm.enable({ snappable: true, allowSelfIntersection: false });
      const handler = () => {
        const latlngs = layer.getLatLngs()[0].map((p) => [p.lat, p.lng]);
        onChange?.(latlngs);
      };
      layer.on('pm:edit', handler);
      layer.on('pm:dragend', handler);
      return () => {
        try { layer.pm.disable(); } catch { /* noop */ }
        layer.off('pm:edit', handler);
        layer.off('pm:dragend', handler);
      };
    }
    try { layer.pm.disable(); } catch { /* noop */ }
    return undefined;
  }, [editable, onChange]);

  if (!abschnitt.polygon || abschnitt.polygon.length < 3) return null;

  return (
    <Polygon
      ref={ref}
      positions={abschnitt.polygon}
      pathOptions={{
        color: farbe.hex,
        fillColor: farbe.hex,
        fillOpacity: editable ? 0.25 : 0.15,
        weight: editable ? 3 : 2,
        opacity: abschnitt.aktiv === false ? 0.4 : 1,
        dashArray: abschnitt.aktiv === false ? '6 4' : null,
      }}
      eventHandlers={{
        click: (e) => {
          // Stop click from bubbling to map (prevents place-mode misfires)
          L.DomEvent.stopPropagation(e);
          onClick?.(abschnitt);
        },
      }}
    >
      <Tooltip permanent direction="center" className="els-abschnitt-tooltip">
        {abschnitt.name}
      </Tooltip>
    </Polygon>
  );
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
  abschnitte = [],
  onMapClick,
  onResourceMove,
  onResourceClick,
  onIncidentMove,
  onAbschnittClick,
  onAbschnittPolygonChange,
  onAbschnittPolygonDrawn,
  onCancelDrawing,
  drawingForAbschnitt = null, // abschnitt object currently being drawn
  editingAbschnitte = false,
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

        <GeomanController
          mode={drawingForAbschnitt ? 'draw' : null}
          color={drawingForAbschnitt ? getFarbe(drawingForAbschnitt.farbe).hex : '#3388ff'}
          onDrawComplete={(latlngs) =>
            onAbschnittPolygonDrawn?.(drawingForAbschnitt, latlngs)
          }
          onCancel={onCancelDrawing}
        />

        {abschnitte
          .filter((a) => Array.isArray(a.polygon) && a.polygon.length >= 3)
          .map((a) => (
            <EditablePolygon
              key={a.id}
              abschnitt={a}
              editable={editingAbschnitte && !clickToPlace && !drawingForAbschnitt}
              onClick={onAbschnittClick}
              onChange={(latlngs) =>
                onAbschnittPolygonChange?.(a.id, latlngs)
              }
            />
          ))}

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
            const label = (r.kuerzel && r.kuerzel.trim())
              || r.name?.split(' ')[0]
              || '';
            const icon = makeResourceIcon({ label, color });
            return (
              <Marker
                key={r.id}
                position={[r.lat, r.lng]}
                icon={icon}
                draggable={draggableResources}
                interactive={!clickToPlace}
                eventHandlers={{
                  click: (e) => {
                    // Suppress Leaflet popup, route to our dialog
                    L.DomEvent.stopPropagation(e);
                    onResourceClick?.(r);
                  },
                  dragend: (e) => {
                    const ll = e.target.getLatLng();
                    onResourceMove?.(r.id, [ll.lat, ll.lng]);
                  },
                }}
              />
            );
          })}
      </MapContainer>
    </div>
  );
}
