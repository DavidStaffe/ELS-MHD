import * as React from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { MapPicker } from '@/components/map/MapPicker';
import { Save } from 'lucide-react';
import { toast } from 'sonner';

const TYP_OPTIONS = [
  { value: 'veranstaltung', label: 'Veranstaltung' },
  { value: 'sanitaetsdienst', label: 'Sanitätsdienst' },
  { value: 'einsatz', label: 'Einsatz' },
  { value: 'uebung', label: 'Übung' },
];

/**
 * EditIncidentDialog – bearbeite Name, Typ, Ort (Text + MapPicker), Beschreibung
 * eines bestehenden Incidents. Lat/Lng/Zoom werden mit-aktualisiert.
 *
 * Props:
 *   open, onOpenChange
 *   incident: das zu editierende Incident
 *   onSave(patch): async — ruft IncidentContext.update auf
 */
export function EditIncidentDialog({ open, onOpenChange, incident, onSave }) {
  const [name, setName] = React.useState('');
  const [typ, setTyp] = React.useState('veranstaltung');
  const [ort, setOrt] = React.useState('');
  const [beschreibung, setBeschreibung] = React.useState('');
  const [location, setLocation] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState(null);

  React.useEffect(() => {
    if (open && incident) {
      setName(incident.name || '');
      setTyp(incident.typ || 'veranstaltung');
      setOrt(incident.ort || '');
      setBeschreibung(incident.beschreibung || '');
      setLocation(
        incident.ort_lat != null
          ? { lat: incident.ort_lat, lng: incident.ort_lng }
          : null,
      );
      setError(null);
    }
  }, [open, incident]);

  if (!incident) return null;

  const handleLocationChange = (loc) => {
    setLocation(loc);
    // Wenn die MapPicker per Reverse-Geocoding eine Adresse liefert UND das
    // Ort-Feld bisher leer war, automatisch uebernehmen.
    if (loc?.address && !ort.trim()) {
      setOrt(loc.address);
    }
  };

  const handleSubmit = async (e) => {
    e?.preventDefault?.();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const patch = {
        name: name.trim(),
        typ,
        ort: ort.trim(),
        beschreibung: beschreibung.trim(),
      };
      if (location?.lat != null && location?.lng != null) {
        patch.ort_lat = location.lat;
        patch.ort_lng = location.lng;
        if (!incident.ort_zoom) patch.ort_zoom = 15;
      } else {
        // Lat/Lng entfernt
        patch.ort_lat = null;
        patch.ort_lng = null;
        patch.ort_zoom = null;
      }
      await onSave(patch);
      toast.success('Incident aktualisiert');
      onOpenChange(false);
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          'Speichern fehlgeschlagen',
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-xl bg-card border-border max-h-[90vh] overflow-y-auto"
        data-testid="edit-incident-dialog"
      >
        <DialogHeader>
          <DialogTitle>Incident bearbeiten</DialogTitle>
          <DialogDescription>
            Aenderungen werden sofort gespeichert und an alle verbundenen
            Clients verteilt.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="ei-name">Name</Label>
            <Input
              id="ei-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              maxLength={120}
              autoFocus
              data-testid="ei-name"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ei-typ">Typ</Label>
            <Select value={typ} onValueChange={setTyp}>
              <SelectTrigger id="ei-typ" data-testid="ei-typ">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TYP_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ei-ort">Ort (Adresse)</Label>
            <Input
              id="ei-ort"
              value={ort}
              onChange={(e) => setOrt(e.target.value)}
              placeholder="z.B. Festplatz Sued, Hamburg"
              maxLength={180}
              data-testid="ei-ort"
            />
          </div>

          <div className="space-y-1.5">
            <Label>Lagekarte</Label>
            <p className="text-caption text-muted-foreground">
              Suche eine Adresse oder klicke auf die Karte. Marker laesst sich
              verschieben. Leer lassen entfernt den Karten-Standort.
            </p>
            <MapPicker
              value={location}
              onChange={handleLocationChange}
              height="220px"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ei-beschreibung">Beschreibung</Label>
            <Textarea
              id="ei-beschreibung"
              value={beschreibung}
              onChange={(e) => setBeschreibung(e.target.value)}
              maxLength={2000}
              rows={3}
              data-testid="ei-beschreibung"
            />
          </div>

          {error && (
            <div
              className="rounded-md border border-status-red/40 bg-status-red/10 px-3 py-2 text-caption text-status-red"
              data-testid="ei-error"
            >
              {error}
            </div>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={busy}
              data-testid="ei-cancel"
            >
              Abbrechen
            </Button>
            <Button
              type="submit"
              disabled={busy || !name.trim()}
              data-testid="ei-save"
            >
              <Save className="h-3.5 w-3.5" />
              {busy ? 'Speichere…' : 'Speichern'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
