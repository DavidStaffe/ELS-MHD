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
import { Checkbox } from '@/components/ui/checkbox';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toLocalInput, fromLocalInput } from '@/lib/time';

const TYPEN = [
  { value: 'veranstaltung', label: 'Veranstaltung' },
  { value: 'sanitaetsdienst', label: 'Sanitaetsdienst' },
  { value: 'uebung', label: 'Uebung' },
  { value: 'einsatz', label: 'Einsatz' },
  { value: 'sonstiges', label: 'Sonstiges' },
];

function defaultStart() {
  return toLocalInput(new Date().toISOString());
}

export function NewIncidentDialog({ open, onOpenChange, onCreate }) {
  const [name, setName] = React.useState('');
  const [typ, setTyp] = React.useState('veranstaltung');
  const [ort, setOrt] = React.useState('');
  const [startLocal, setStartLocal] = React.useState(defaultStart);
  const [beschreibung, setBeschreibung] = React.useState('');
  const [isPlanned, setIsPlanned] = React.useState(false);
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState(null);

  const reset = React.useCallback(() => {
    setName('');
    setTyp('veranstaltung');
    setOrt('');
    setStartLocal(defaultStart());
    setBeschreibung('');
    setIsPlanned(false);
    setError(null);
  }, []);

  React.useEffect(() => {
    if (open) reset();
  }, [open, reset]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim() || name.trim().length < 2) {
      setError('Bitte einen Namen mit mindestens 2 Zeichen angeben.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const payload = {
        name: name.trim(),
        typ,
        ort: ort.trim(),
        beschreibung: beschreibung.trim(),
        status: isPlanned ? 'geplant' : 'operativ',
        demo: false,
        start_at: fromLocalInput(startLocal),
      };
      await onCreate(payload);
      onOpenChange?.(false);
    } catch (err) {
      setError(
        err?.response?.data?.detail || err?.message || 'Fehler beim Anlegen',
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-lg bg-card border-border"
        data-testid="new-incident-dialog"
      >
        <DialogHeader>
          <DialogTitle className="text-heading">
            Neuen Incident anlegen
          </DialogTitle>
          <DialogDescription className="text-body text-muted-foreground">
            Alle Angaben koennen spaeter ergaenzt werden. Der Incident wird
            automatisch als aktiv markiert.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="nin-name">
              Name <span className="text-status-red">*</span>
            </Label>
            <Input
              id="nin-name"
              data-testid="nin-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="z.B. Stadtfest 2026"
              autoFocus
              required
              minLength={2}
              maxLength={120}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="nin-typ">Typ</Label>
              <Select value={typ} onValueChange={setTyp}>
                <SelectTrigger id="nin-typ" data-testid="nin-typ">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TYPEN.map((t) => (
                    <SelectItem key={t.value} value={t.value}>
                      {t.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="nin-start">Start</Label>
              <Input
                id="nin-start"
                data-testid="nin-start"
                type="datetime-local"
                value={startLocal}
                onChange={(e) => setStartLocal(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="nin-ort">Ort</Label>
            <Input
              id="nin-ort"
              data-testid="nin-ort"
              value={ort}
              onChange={(e) => setOrt(e.target.value)}
              placeholder="z.B. Festplatz Sued"
              maxLength={180}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="nin-beschreibung">Kurzbeschreibung</Label>
            <Textarea
              id="nin-beschreibung"
              data-testid="nin-beschreibung"
              value={beschreibung}
              onChange={(e) => setBeschreibung(e.target.value)}
              rows={2}
              maxLength={2000}
              placeholder="Optional"
            />
          </div>

          <div className="flex items-start gap-2 rounded-md border border-border bg-surface-sunken px-3 py-2.5">
            <Checkbox
              id="nin-planned"
              checked={isPlanned}
              onCheckedChange={(v) => setIsPlanned(Boolean(v))}
              data-testid="nin-planned"
            />
            <div className="space-y-0.5">
              <Label htmlFor="nin-planned">Als geplant anlegen</Label>
              <p className="text-caption text-muted-foreground">
                Geplante Incidents koennen vorbereitet werden. Patienten und
                Transporte sind erst nach Umschalten auf "Operativ" verfuegbar.
              </p>
            </div>
          </div>

          {error && (
            <div
              className="rounded-md border border-status-red/40 bg-status-red/10 px-3 py-2 text-caption text-status-red"
              data-testid="nin-error"
            >
              {error}
            </div>
          )}

          <DialogFooter className="gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange?.(false)}
              disabled={submitting}
              data-testid="nin-cancel"
            >
              Abbrechen
            </Button>
            <Button
              type="submit"
              disabled={submitting}
              data-testid="nin-submit"
            >
              {submitting ? 'Wird angelegt…' : 'Anlegen & aktivieren'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
