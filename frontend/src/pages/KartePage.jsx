import * as React from 'react';
import { useNavigate } from 'react-router-dom';
import { useIncidents } from '@/context/IncidentContext';
import { useOps } from '@/context/OpsContext';
import { useRole } from '@/context/RoleContext';
import { IncidentMap } from '@/components/map/IncidentMap';
import { MapPicker } from '@/components/map/MapPicker';
import { Button } from '@/components/ui/button';
import { StatusBadge, KpiTile } from '@/components/primitives';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  listAbschnitte,
  createAbschnitt,
  updateAbschnitt,
  listDiveraVehicles,
} from '@/lib/api';
import { ABSCHNITT_FARBEN, getFarbe } from '@/lib/abschnitt-meta';
import { FMS_STATUS, fmsMeta } from '@/lib/fms-status';
import { DiveraPanel } from '@/components/map/DiveraPanel';
import { FmsHistory } from '@/components/map/FmsHistory';
import { FmsAlertSidebarPanel } from '@/components/fms/FmsAlertSidebarPanel';
import { toast } from 'sonner';
import {
  ArrowLeft,
  MapPin,
  MapPinned,
  Plus,
  Lock,
  Save,
  Trash2,
  Settings2,
  Pencil,
  X,
  Layers,
  Check,
  Edit3,
} from 'lucide-react';

const RESOURCE_KAT_LABEL = {
  uhs: 'UHS-Team',
  evt: 'EVT',
  rtw: 'RTW',
  ktw: 'KTW',
  nef: 'NEF',
  sonstiges: 'Sonstiges',
};

function ResourceLegend() {
  return (
    <div className="els-surface p-3 text-caption" data-testid="map-fms-legend">
      <div className="font-medium text-foreground mb-2">FMS-Legende</div>
      <ul className="space-y-1">
        {Object.entries(FMS_STATUS).map(([key, m]) => (
          <li key={key} className="flex items-center gap-2">
            <span
              className="inline-block w-3 h-3 rounded-full"
              style={{ background: m.color }}
            />
            <span className="font-mono text-foreground w-4">{key}</span>
            <span className="text-muted-foreground">{m.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function EditIncidentLocationDialog({
  open,
  onOpenChange,
  incident,
  onSave,
}) {
  const [location, setLocation] = React.useState(null);
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    if (open && incident) {
      setLocation(
        incident.ort_lat != null
          ? { lat: incident.ort_lat, lng: incident.ort_lng }
          : null,
      );
    }
  }, [open, incident]);

  const handleSave = async () => {
    setBusy(true);
    try {
      await onSave(
        location
          ? { ort_lat: location.lat, ort_lng: location.lng, ort_zoom: 15 }
          : { ort_lat: null, ort_lng: null, ort_zoom: null },
      );
      onOpenChange(false);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-xl bg-card border-border max-h-[90vh] overflow-y-auto"
        data-testid="map-edit-location-dialog"
      >
        <DialogHeader>
          <DialogTitle>Einsatz-Ort bearbeiten</DialogTitle>
          <DialogDescription>
            Suche eine Adresse oder klicke auf die Karte. Aenderungen werden
            sofort gespeichert und an alle verbundenen Clients ausgespielt.
          </DialogDescription>
        </DialogHeader>
        <MapPicker
          value={location}
          onChange={setLocation}
          height="300px"
        />
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={busy}
            data-testid="map-edit-cancel"
          >
            Abbrechen
          </Button>
          <Button onClick={handleSave} disabled={busy} data-testid="map-edit-save">
            <Save className="h-3.5 w-3.5" />
            {busy ? 'Speichere…' : 'Speichern'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function EditResourceDialog({ open, onOpenChange, resource, onSave, onRemove }) {
  const [fmsStatus, setFmsStatus] = React.useState('none');
  const [diveraId, setDiveraId] = React.useState('');
  const [vehicles, setVehicles] = React.useState([]);
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    if (open && resource) {
      setFmsStatus(
        resource.fms_status !== null && resource.fms_status !== undefined
          ? String(resource.fms_status)
          : 'none',
      );
      setDiveraId(resource.divera_id || '');
    }
  }, [open, resource]);

  React.useEffect(() => {
    if (!open) return;
    (async () => {
      try {
        const v = await listDiveraVehicles();
        setVehicles(v);
      } catch {
        setVehicles([]);
      }
    })();
  }, [open]);

  if (!resource) return null;

  const linkedVehicle = diveraId
    ? vehicles.find((v) => String(v.id) === String(diveraId))
    : null;

  const handleSave = async () => {
    setBusy(true);
    try {
      await onSave({
        fms_status: fmsStatus === 'none' ? null : Number(fmsStatus),
        divera_id: diveraId.trim() || null,
      });
      onOpenChange(false);
    } finally {
      setBusy(false);
    }
  };

  const handleRemoveFromMap = async () => {
    setBusy(true);
    try {
      await onRemove();
      onOpenChange(false);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-md bg-card border-border max-h-[90vh] overflow-y-auto"
        data-testid="map-edit-resource-dialog"
      >
        <DialogHeader>
          <DialogTitle>{resource.name}</DialogTitle>
          <DialogDescription>
            Kategorie: {RESOURCE_KAT_LABEL[resource.kategorie] || resource.kategorie} ·
            Position{' '}
            <span className="font-mono">
              {resource.lat?.toFixed(5)}, {resource.lng?.toFixed(5)}
            </span>
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="rd-divera">Divera-Fahrzeug verknuepfen</Label>
            <Select
              value={diveraId || 'none'}
              onValueChange={(v) => setDiveraId(v === 'none' ? '' : v)}
              disabled={vehicles.length === 0}
            >
              <SelectTrigger id="rd-divera" data-testid="map-resource-divera">
                <SelectValue placeholder="— nicht verknuepft —" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">— nicht verknuepft —</SelectItem>
                {vehicles.map((v) => (
                  <SelectItem key={v.id} value={String(v.id)}>
                    <span className="font-medium">{v.name}</span>
                    <span className="ml-2 text-muted-foreground text-xs">
                      ({v.shortname || v.fullname})
                    </span>
                    {v.fmsstatus !== null && v.fmsstatus !== undefined && (
                      <span className="ml-2 font-mono text-xs">FMS {v.fmsstatus}</span>
                    )}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {vehicles.length === 0 ? (
              <p className="text-caption text-muted-foreground">
                Keine Divera-Fahrzeuge verfuegbar (API-Key fehlt oder kein Zugriff).
              </p>
            ) : linkedVehicle ? (
              <p className="text-caption text-muted-foreground">
                Verknuepft mit{' '}
                <span className="font-mono text-foreground">{linkedVehicle.name}</span>
                {linkedVehicle.fmsstatus !== null && (
                  <>
                    {' · aktueller FMS '}
                    <span
                      className="font-mono font-semibold"
                      style={{ color: fmsMeta(linkedVehicle.fmsstatus)?.color }}
                    >
                      {linkedVehicle.fmsstatus}
                    </span>
                  </>
                )}
              </p>
            ) : (
              <p className="text-caption text-muted-foreground">
                Wenn verknuepft, ueberschreibt das Divera-Polling den FMS-Status.
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="rd-fms">FMS-Status (manuell)</Label>
            <Select value={fmsStatus} onValueChange={setFmsStatus} disabled={Boolean(diveraId)}>
              <SelectTrigger id="rd-fms" data-testid="map-resource-fms">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">— kein FMS gesetzt —</SelectItem>
                {Object.entries(FMS_STATUS).map(([key, m]) => (
                  <SelectItem key={key} value={key}>
                    <span className="font-mono mr-2">{key}</span>
                    {m.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-caption text-muted-foreground">
              {diveraId
                ? 'Manuell deaktiviert, da Divera-Verknuepfung gesetzt ist.'
                : 'Wird vom Divera-Polling ueberschrieben, sobald eine Verknuepfung gesetzt ist.'}
            </p>
          </div>

          {/* FMS-Verlauf fuer diese Ressource */}
          <div className="border-t border-border pt-3">
            <FmsHistory
              incidentId={resource.incident_id}
              resourceId={resource.id}
              showResourceName={false}
              limit={20}
              compact
            />
          </div>
        </div>

        <DialogFooter className="flex-row justify-between gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleRemoveFromMap}
            disabled={busy}
            className="text-muted-foreground hover:text-destructive"
            data-testid="map-resource-unplace"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Von Karte entfernen
          </Button>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={busy}
            >
              Abbrechen
            </Button>
            <Button
              onClick={handleSave}
              disabled={busy}
              data-testid="map-resource-save"
            >
              {busy ? 'Speichere…' : 'Speichern'}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function KartePage() {
  const { activeIncident, update: updateIncident } = useIncidents();
  const { resources, updResource } = useOps();
  const { can } = useRole();
  const navigate = useNavigate();

  const [editLocation, setEditLocation] = React.useState(false);
  const [editResource, setEditResource] = React.useState(null);
  const [placeMode, setPlaceMode] = React.useState(null); // resource id or null

  // Phase 2 – Abschnitts-Polygone
  const [abschnitte, setAbschnitte] = React.useState([]);
  const [drawingForAbschnitt, setDrawingForAbschnitt] = React.useState(null);
  const [editingAbschnitte, setEditingAbschnitte] = React.useState(false);
  const [pickerOpen, setPickerOpen] = React.useState(false);
  const [editAbschnitt, setEditAbschnitt] = React.useState(null);

  const refreshAbschnitte = React.useCallback(async () => {
    if (!activeIncident?.id) return;
    try {
      const list = await listAbschnitte(activeIncident.id);
      setAbschnitte(list);
    } catch (e) {
      console.warn('Abschnitte konnten nicht geladen werden', e);
    }
  }, [activeIncident?.id]);

  React.useEffect(() => {
    refreshAbschnitte();
  }, [refreshAbschnitte]);

  const canEdit = can('incident.update');
  const canEditResource = can('resource.update');
  const isArchived = activeIncident?.status === 'abgeschlossen';

  const unplacedResources = React.useMemo(
    () => resources.filter((r) => r.lat == null || r.lng == null),
    [resources],
  );

  const activeOnMap = resources.filter(
    (r) => r.lat != null && r.lng != null,
  ).length;
  const fmsCounts = React.useMemo(() => {
    const c = { verfuegbar: 0, einsatz: 0, sprechwunsch: 0, offline: 0, wartung: 0 };
    for (const r of resources) {
      const m = fmsMeta(r.fms_status);
      if (m && c[m.group] !== undefined) c[m.group]++;
    }
    return c;
  }, [resources]);

  if (!activeIncident) {
    return (
      <div className="mx-auto max-w-2xl p-6">
        <div className="els-surface p-6 text-center" data-testid="karte-no-incident">
          <h2 className="text-display">Kein Incident aktiv</h2>
          <p className="mt-2 text-muted-foreground">
            Waehle zunaechst einen Incident aus der Uebersicht.
          </p>
          <Button className="mt-4" onClick={() => navigate('/')}>
            <ArrowLeft className="h-4 w-4" />
            Zur Incident-Uebersicht
          </Button>
        </div>
      </div>
    );
  }

  const handleSaveIncidentLocation = async (patch) => {
    try {
      await updateIncident(activeIncident.id, patch);
      toast.success('Lage-Ort aktualisiert');
    } catch (e) {
      toast.error('Speichern fehlgeschlagen');
    }
  };

  const handleIncidentDrag = async ([lat, lng]) => {
    if (!canEdit || isArchived) return;
    try {
      await updateIncident(activeIncident.id, {
        ort_lat: lat,
        ort_lng: lng,
      });
      toast.success('Lage-Ort verschoben');
    } catch {
      toast.error('Verschieben fehlgeschlagen');
    }
  };

  const handleResourceMove = async (id, [lat, lng]) => {
    if (!canEditResource || isArchived) return;
    try {
      await updResource(id, { lat, lng });
    } catch {
      toast.error('Ressource konnte nicht verschoben werden');
    }
  };

  const handleMapClickPlace = async ([lat, lng]) => {
    if (!placeMode) return;
    try {
      await updResource(placeMode, { lat, lng });
      toast.success('Ressource platziert');
      setPlaceMode(null);
    } catch {
      toast.error('Platzieren fehlgeschlagen');
    }
  };

  const handleResourceClick = (r) => {
    if (placeMode) return;
    setEditResource(r);
  };

  // ----- Phase 2: Abschnitt polygon handlers -----
  const startDrawing = (abschnitt) => {
    setEditingAbschnitte(false);
    setPlaceMode(null);
    setDrawingForAbschnitt(abschnitt);
    setPickerOpen(false);
    toast.info(`Polygon fuer "${abschnitt.name}" zeichnen – Doppelklick beendet`);
  };

  const handlePolygonDrawn = async (abschnitt, latlngs) => {
    if (!abschnitt || latlngs.length < 3) {
      setDrawingForAbschnitt(null);
      return;
    }
    try {
      await updateAbschnitt(abschnitt.id, { polygon: latlngs });
      toast.success(`Polygon fuer "${abschnitt.name}" gespeichert`);
      await refreshAbschnitte();
    } catch (e) {
      toast.error('Polygon konnte nicht gespeichert werden');
    } finally {
      setDrawingForAbschnitt(null);
    }
  };

  const handlePolygonChange = async (id, latlngs) => {
    if (latlngs.length < 3) return;
    try {
      await updateAbschnitt(id, { polygon: latlngs });
      // Optimistic local update
      setAbschnitte((prev) =>
        prev.map((a) => (a.id === id ? { ...a, polygon: latlngs } : a)),
      );
    } catch (e) {
      toast.error('Speichern fehlgeschlagen');
    }
  };

  const handleAbschnittClick = (abschnitt) => {
    if (drawingForAbschnitt) return;
    setEditAbschnitt(abschnitt);
  };

  const handleClearPolygon = async (abschnitt) => {
    try {
      await updateAbschnitt(abschnitt.id, { polygon: null });
      toast.success(`Polygon entfernt: ${abschnitt.name}`);
      await refreshAbschnitte();
    } catch {
      toast.error('Entfernen fehlgeschlagen');
    }
  };

  const handleCreateAndDraw = async (data) => {
    try {
      const created = await createAbschnitt(activeIncident.id, data);
      await refreshAbschnitte();
      startDrawing(created);
    } catch (e) {
      toast.error('Abschnitt konnte nicht angelegt werden');
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-3.5rem)]">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-3 border-b border-border bg-surface-sunken">
        <div className="min-w-0">
          <div className="text-caption uppercase tracking-wider text-muted-foreground flex items-center gap-2">
            <MapPinned className="h-3 w-3" />
            Lagekarte
            {isArchived && (
              <StatusBadge tone="gray" variant="soft" size="sm">
                <Lock className="h-3 w-3" />
                archiviert
              </StatusBadge>
            )}
          </div>
          <h1 className="text-heading truncate" data-testid="karte-title">
            {activeIncident.name}
          </h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setEditLocation(true)}
            disabled={!canEdit || isArchived}
            data-testid="btn-edit-location"
            title="Einsatz-Ort bearbeiten"
          >
            <Settings2 className="h-4 w-4" />
            Ort bearbeiten
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate('/lage')}
            data-testid="btn-back-lage"
          >
            <ArrowLeft className="h-4 w-4" />
            Zur Lage
          </Button>
        </div>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2 px-6 py-2 border-b border-border bg-surface-sunken/40">
        <KpiTile
          label="Auf Karte"
          value={activeOnMap}
          unit={`/${resources.length}`}
          tone="default"
          testId="kpi-on-map"
        />
        <KpiTile
          label="Verfügbar"
          value={fmsCounts.verfuegbar}
          tone="green"
          testId="kpi-fms-verfuegbar"
        />
        <KpiTile
          label="Im Einsatz"
          value={fmsCounts.einsatz}
          tone="yellow"
          testId="kpi-fms-einsatz"
        />
        <KpiTile
          label="Sprechw."
          value={fmsCounts.sprechwunsch}
          tone="red"
          testId="kpi-fms-sprechwunsch"
        />
        <KpiTile
          label="Offline/Wartung"
          value={fmsCounts.offline + fmsCounts.wartung}
          tone="gray"
          testId="kpi-fms-offline"
        />
      </div>

      {/* Map + Sidebar */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[1fr_320px] overflow-hidden">
        <div className="relative">
          {placeMode && (
            <div
              className="absolute top-3 left-1/2 -translate-x-1/2 z-[400] rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground shadow-lg flex items-center gap-2"
              data-testid="place-mode-banner"
            >
              <MapPin className="h-4 w-4" />
              Klicke auf die Karte, um die Ressource zu platzieren
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setPlaceMode(null)}
                className="h-6 ml-2 hover:bg-primary-foreground/20"
              >
                Abbrechen
              </Button>
            </div>
          )}
          {drawingForAbschnitt && (
            <div
              className="absolute top-3 left-1/2 -translate-x-1/2 z-[400] rounded-md px-3 py-2 text-sm font-medium text-white shadow-lg flex items-center gap-2"
              style={{ background: getFarbe(drawingForAbschnitt.farbe).hex }}
              data-testid="draw-mode-banner"
            >
              <Pencil className="h-4 w-4" />
              Polygon „{drawingForAbschnitt.name}" zeichnen — Klicks setzen
              Punkte, Doppelklick beendet, ESC bricht ab
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setDrawingForAbschnitt(null)}
                className="h-6 ml-2 hover:bg-white/20 text-white"
              >
                <X className="h-3.5 w-3.5" />
              </Button>
            </div>
          )}
          {editingAbschnitte && !drawingForAbschnitt && (
            <div
              className="absolute top-3 right-3 z-[400] rounded-md bg-amber-600 px-3 py-1.5 text-xs font-medium text-white shadow-lg flex items-center gap-2"
              data-testid="edit-mode-banner"
            >
              <Edit3 className="h-3.5 w-3.5" />
              Edit-Modus — Vertices ziehen, Rechtsklick loescht Punkt
            </div>
          )}
          <IncidentMap
            incident={activeIncident}
            resources={resources}
            abschnitte={abschnitte}
            draggableIncident={canEdit && !isArchived && !drawingForAbschnitt}
            draggableResources={
              canEditResource && !isArchived && !placeMode && !drawingForAbschnitt
            }
            clickToPlace={Boolean(placeMode)}
            editingAbschnitte={editingAbschnitte && canEdit && !isArchived}
            drawingForAbschnitt={drawingForAbschnitt}
            onMapClick={handleMapClickPlace}
            onIncidentMove={handleIncidentDrag}
            onResourceMove={handleResourceMove}
            onResourceClick={handleResourceClick}
            onAbschnittClick={handleAbschnittClick}
            onAbschnittPolygonDrawn={handlePolygonDrawn}
            onAbschnittPolygonChange={handlePolygonChange}
            onCancelDrawing={() => setDrawingForAbschnitt(null)}
            height="100%"
            showAttribution
          />
        </div>

        <aside
          className="border-t lg:border-t-0 lg:border-l border-border bg-surface-sunken/60 overflow-y-auto p-3 space-y-3"
          data-testid="map-sidebar"
        >
          {/* Sprechwunsch-Alarm-Panel (nur sichtbar wenn offene FMS-5/0-Alarme) */}
          <FmsAlertSidebarPanel />

          {/* 1. Divera 24/7 ------------------------------------------- */}
          <DiveraPanel
            incidentId={activeIncident.id}
            disabled={isArchived}
            onChange={() => {
              // refresh resources via OpsContext (already via SSE, but trigger manual reload)
            }}
          />

          {/* 2. FMS-Legende ------------------------------------------- */}
          <ResourceLegend />

          {/* 3. FMS-Verlauf (nur letzte 5, voller Verlauf im Funktagebuch) */}
          <div className="els-surface p-3" data-testid="map-fms-history-panel">
            <FmsHistory
              incidentId={activeIncident.id}
              limit={5}
              compact
            />
            <div className="mt-2 text-right">
              <Button
                type="button"
                variant="link"
                size="sm"
                onClick={() => navigate('/funktagebuch')}
                data-testid="map-fms-history-fulllink"
                className="h-auto p-0 text-caption text-primary"
              >
                Vollstaendiger Verlauf im Funktagebuch →
              </Button>
            </div>
          </div>

          {/* 4. Abschnitte -------------------------------------------- */}
          <div className="els-surface p-3" data-testid="map-abschnitte-panel">
            <div className="flex items-center justify-between mb-2">
              <div className="text-caption uppercase tracking-wider text-muted-foreground flex items-center gap-1">
                <Layers className="h-3 w-3" />
                Abschnitte ({abschnitte.length})
              </div>
              <div className="flex gap-1">
                <Button
                  type="button"
                  size="sm"
                  variant={editingAbschnitte ? 'default' : 'outline'}
                  onClick={() => {
                    setEditingAbschnitte((v) => !v);
                    setDrawingForAbschnitt(null);
                    setPlaceMode(null);
                  }}
                  disabled={!canEdit || isArchived}
                  data-testid="btn-edit-polygons"
                  title="Polygone bearbeiten (Vertices ziehen)"
                  className="h-7"
                >
                  <Edit3 className="h-3.5 w-3.5" />
                  {editingAbschnitte ? 'Fertig' : 'Editieren'}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => setPickerOpen(true)}
                  disabled={!canEdit || isArchived || Boolean(drawingForAbschnitt)}
                  data-testid="btn-draw-polygon"
                  className="h-7"
                  title="Neues Polygon zeichnen"
                >
                  <Pencil className="h-3.5 w-3.5" />
                  Zeichnen
                </Button>
              </div>
            </div>
            {abschnitte.length === 0 ? (
              <div className="text-caption text-muted-foreground italic">
                Keine Abschnitte. Lege einen unter „Abschnitte" an oder klicke
                „Zeichnen".
              </div>
            ) : (
              <ul className="space-y-1">
                {abschnitte.map((a) => {
                  const f = getFarbe(a.farbe);
                  const hasPolygon = Array.isArray(a.polygon) && a.polygon.length >= 3;
                  return (
                    <li
                      key={a.id}
                      className="flex items-center gap-2 rounded-md bg-surface-raised px-2 py-1.5"
                      data-testid={`abschnitt-row-${a.id}`}
                    >
                      <span
                        className="inline-block h-3 w-3 rounded-sm shrink-0"
                        style={{ background: f.hex }}
                      />
                      <span
                        className={`flex-1 text-sm truncate ${
                          a.aktiv === false ? 'text-muted-foreground italic' : ''
                        }`}
                      >
                        {a.name}
                      </span>
                      {hasPolygon ? (
                        <StatusBadge tone="green" variant="soft" size="sm">
                          Polygon
                        </StatusBadge>
                      ) : (
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          className="h-6 px-2 text-xs"
                          onClick={() => startDrawing(a)}
                          disabled={!canEdit || isArchived}
                          data-testid={`btn-draw-abschnitt-${a.id}`}
                          title="Polygon zeichnen"
                        >
                          <Pencil className="h-3 w-3" />
                          zeichnen
                        </Button>
                      )}
                      {hasPolygon && (
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          className="h-6 w-6 p-0 text-muted-foreground hover:text-destructive"
                          onClick={() => handleClearPolygon(a)}
                          disabled={!canEdit || isArchived}
                          data-testid={`btn-clear-abschnitt-${a.id}`}
                          title="Polygon entfernen"
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          {unplacedResources.length > 0 && (
            <div className="els-surface p-3" data-testid="map-resources-unplaced">
              <div className="text-caption uppercase tracking-wider text-muted-foreground mb-2">
                Nicht platziert ({unplacedResources.length})
              </div>
              <ul className="space-y-1.5">
                {unplacedResources.map((r) => (
                  <li
                    key={r.id}
                    className="flex items-center gap-2 rounded-md bg-surface-raised px-2.5 py-1.5"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium truncate">{r.name}</div>
                      <div className="text-caption text-muted-foreground">
                        {RESOURCE_KAT_LABEL[r.kategorie] || r.kategorie}
                      </div>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => setPlaceMode(r.id)}
                      disabled={!canEditResource || isArchived || placeMode === r.id}
                      data-testid={`btn-place-${r.id}`}
                      title="Auf Karte platzieren"
                    >
                      <Plus className="h-3.5 w-3.5" />
                      Platzieren
                    </Button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="els-surface p-3" data-testid="map-hints">
            <div className="text-caption uppercase tracking-wider text-muted-foreground mb-1">
              Tipps
            </div>
            <ul className="text-caption text-muted-foreground space-y-1 list-disc list-inside">
              <li>Marker draggen, um Position zu aendern</li>
              <li>Auf Pin klicken fuer FMS-Status</li>
              <li>Incident-Pin verschiebt Karten-Zentrum</li>
            </ul>
          </div>
        </aside>
      </div>

      <EditIncidentLocationDialog
        open={editLocation}
        onOpenChange={setEditLocation}
        incident={activeIncident}
        onSave={handleSaveIncidentLocation}
      />
      <EditResourceDialog
        open={editResource !== null}
        onOpenChange={(v) => !v && setEditResource(null)}
        resource={editResource}
        onSave={async (patch) => {
          await updResource(editResource.id, patch);
          toast.success('Ressource aktualisiert');
        }}
        onRemove={async () => {
          await updResource(editResource.id, { lat: null, lng: null });
          toast.success('Von Karte entfernt');
        }}
      />
      <AbschnittPickerDialog
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        abschnitte={abschnitte}
        onPick={(a) => startDrawing(a)}
        onCreate={handleCreateAndDraw}
      />
      <EditAbschnittDialog
        open={editAbschnitt !== null}
        onOpenChange={(v) => !v && setEditAbschnitt(null)}
        abschnitt={editAbschnitt}
        onSave={async (patch) => {
          try {
            await updateAbschnitt(editAbschnitt.id, patch);
            toast.success('Abschnitt aktualisiert');
            await refreshAbschnitte();
            setEditAbschnitt(null);
          } catch {
            toast.error('Speichern fehlgeschlagen');
          }
        }}
        onClearPolygon={async () => {
          try {
            await updateAbschnitt(editAbschnitt.id, { polygon: null });
            toast.success('Polygon entfernt');
            await refreshAbschnitte();
            setEditAbschnitt(null);
          } catch {
            toast.error('Entfernen fehlgeschlagen');
          }
        }}
        onRedraw={() => {
          const target = editAbschnitt;
          setEditAbschnitt(null);
          startDrawing(target);
        }}
        canEdit={canEdit && !isArchived}
      />
    </div>
  );
}

function AbschnittPickerDialog({ open, onOpenChange, abschnitte, onPick, onCreate }) {
  const [newName, setNewName] = React.useState('');
  const [newFarbe, setNewFarbe] = React.useState('blue');
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    if (open) {
      setNewName('');
      setNewFarbe('blue');
    }
  }, [open]);

  const withoutPolygon = abschnitte.filter(
    (a) => !Array.isArray(a.polygon) || a.polygon.length < 3,
  );

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setBusy(true);
    try {
      await onCreate({ name: newName.trim(), farbe: newFarbe });
      onOpenChange(false);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-md bg-card border-border"
        data-testid="abschnitt-picker-dialog"
      >
        <DialogHeader>
          <DialogTitle>Polygon zeichnen</DialogTitle>
          <DialogDescription>
            Waehle einen bestehenden Abschnitt ohne Polygon oder lege einen
            neuen an. Danach setzt du im Karten-Modus Punkte und beendest mit
            Doppelklick.
          </DialogDescription>
        </DialogHeader>

        {withoutPolygon.length > 0 && (
          <div className="space-y-1.5">
            <div className="text-caption uppercase tracking-wider text-muted-foreground">
              Bestehende Abschnitte ohne Polygon
            </div>
            <ul className="space-y-1">
              {withoutPolygon.map((a) => {
                const f = getFarbe(a.farbe);
                return (
                  <li key={a.id}>
                    <button
                      type="button"
                      onClick={() => onPick(a)}
                      data-testid={`pick-abschnitt-${a.id}`}
                      className="w-full flex items-center gap-2 rounded-md border border-border bg-surface-raised px-2.5 py-1.5 text-left hover:border-primary/60 els-focus-ring"
                    >
                      <span
                        className="inline-block h-3 w-3 rounded-sm shrink-0"
                        style={{ background: f.hex }}
                      />
                      <span className="flex-1 text-sm">{a.name}</span>
                      <Pencil className="h-3.5 w-3.5 text-muted-foreground" />
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        <div className="border-t border-border pt-3 space-y-2">
          <div className="text-caption uppercase tracking-wider text-muted-foreground">
            Neuen Abschnitt anlegen
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="picker-name">Name</Label>
            <Input
              id="picker-name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="z.B. BHP Süd"
              data-testid="picker-new-name"
              autoFocus
            />
          </div>
          <div className="space-y-1.5">
            <Label>Farbe</Label>
            <div className="flex flex-wrap gap-1.5">
              {ABSCHNITT_FARBEN.map((f) => (
                <button
                  key={f.key}
                  type="button"
                  onClick={() => setNewFarbe(f.key)}
                  data-testid={`picker-farbe-${f.key}`}
                  aria-label={f.label}
                  title={f.label}
                  className={`h-7 w-7 rounded-md border-2 transition-all ${
                    newFarbe === f.key
                      ? 'border-foreground scale-110'
                      : 'border-transparent opacity-70 hover:opacity-100'
                  }`}
                  style={{ background: f.hex }}
                />
              ))}
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={busy}
          >
            Abbrechen
          </Button>
          <Button
            onClick={handleCreate}
            disabled={busy || !newName.trim()}
            data-testid="picker-create-draw"
          >
            <Plus className="h-3.5 w-3.5" />
            Anlegen & zeichnen
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function EditAbschnittDialog({
  open,
  onOpenChange,
  abschnitt,
  onSave,
  onClearPolygon,
  onRedraw,
  canEdit,
}) {
  const [name, setName] = React.useState('');
  const [farbe, setFarbe] = React.useState('blue');
  const [aktiv, setAktiv] = React.useState(true);
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    if (open && abschnitt) {
      setName(abschnitt.name || '');
      setFarbe(abschnitt.farbe || 'blue');
      setAktiv(abschnitt.aktiv !== false);
    }
  }, [open, abschnitt]);

  if (!abschnitt) return null;
  const hasPolygon = Array.isArray(abschnitt.polygon) && abschnitt.polygon.length >= 3;

  const handleSave = async () => {
    setBusy(true);
    try {
      await onSave({ name: name.trim(), farbe, aktiv });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-md bg-card border-border"
        data-testid="edit-abschnitt-dialog"
      >
        <DialogHeader>
          <DialogTitle>Abschnitt bearbeiten</DialogTitle>
          <DialogDescription>
            Name und Farbe aenderbar. Polygon kannst du neu zeichnen oder
            entfernen.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          <div className="space-y-1.5">
            <Label htmlFor="ea-name">Name</Label>
            <Input
              id="ea-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              data-testid="ea-name"
              disabled={!canEdit}
            />
          </div>
          <div className="space-y-1.5">
            <Label>Farbe</Label>
            <div className="flex flex-wrap gap-1.5">
              {ABSCHNITT_FARBEN.map((f) => (
                <button
                  key={f.key}
                  type="button"
                  onClick={() => setFarbe(f.key)}
                  disabled={!canEdit}
                  aria-label={f.label}
                  title={f.label}
                  data-testid={`ea-farbe-${f.key}`}
                  className={`h-7 w-7 rounded-md border-2 transition-all ${
                    farbe === f.key
                      ? 'border-foreground scale-110'
                      : 'border-transparent opacity-70 hover:opacity-100'
                  } disabled:opacity-40`}
                  style={{ background: f.hex }}
                />
              ))}
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={aktiv}
              onChange={(e) => setAktiv(e.target.checked)}
              disabled={!canEdit}
              data-testid="ea-aktiv"
            />
            <span>Aktiv (inaktive Abschnitte sind gedimmt dargestellt)</span>
          </label>
        </div>

        <DialogFooter className="flex-row justify-between gap-2 flex-wrap">
          <div className="flex gap-2">
            {hasPolygon && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onClearPolygon}
                disabled={busy || !canEdit}
                className="text-muted-foreground hover:text-destructive"
                data-testid="ea-clear-polygon"
              >
                <Trash2 className="h-3.5 w-3.5" />
                Polygon entfernen
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={onRedraw}
              disabled={busy || !canEdit}
              data-testid="ea-redraw"
            >
              <Pencil className="h-3.5 w-3.5" />
              {hasPolygon ? 'Neu zeichnen' : 'Zeichnen'}
            </Button>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={busy}
            >
              Abbrechen
            </Button>
            <Button
              onClick={handleSave}
              disabled={busy || !canEdit || !name.trim()}
              data-testid="ea-save"
            >
              <Check className="h-3.5 w-3.5" />
              Speichern
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
