import * as React from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { SICHTUNG } from '@/lib/patient-meta';
import { Plus, Keyboard, Loader2 } from 'lucide-react';
import { useIncidents } from '@/context/IncidentContext';
import { listResources } from '@/lib/api';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";

/**
 * QuickEntryBar – Schnellerfassung am unteren Bildschirmrand.
 * 2-Tap-Flow: [Sichtung waehlen] -> Patient sofort mit Sichtung+Status=in_behandlung angelegt.
 * Zusaetzlich: "+" Button oeffnet den ausfuehrlicheren Dialog.
 *
 * Tastaturkuerzel: 1 = S1, 2 = S2, 3 = S3, 4 = S4, N = Neu (Dialog).
 */
export function QuickEntryBar({
  onQuickCreate,
  onOpenDialog,
  disabled = false,
  className,
}) {
  const { activeIncident } = useIncidents();
  const [busyKey, setBusyKey] = React.useState(null);
  const [dummyPromptOpen, setDummyPromptOpen] = React.useState(false);
  const [dummyResource, setDummyResource] = React.useState('');
  const [resources, setResources] = React.useState([]);
  const [loadingResources, setLoadingResources] = React.useState(false);

  React.useEffect(() => {
    if (dummyPromptOpen && activeIncident) {
      setLoadingResources(true);
      listResources(activeIncident.id)
        .then((data) => setResources(data))
        .catch(() => {})
        .finally(() => setLoadingResources(false));
    }
  }, [dummyPromptOpen, activeIncident]);

  const handleQuick = React.useCallback(
    async (level) => {
      if (busyKey || disabled) return;
      setBusyKey(level);
      try {
        await onQuickCreate?.({ sichtung: level });
      } finally {
        setBusyKey(null);
      }
    },
    [busyKey, disabled, onQuickCreate],
  );

  React.useEffect(() => {
    const handler = (e) => {
      if (disabled) return;
      // Nicht auslösen in Eingabefeldern
      const target = e.target;
      const tag = target?.tagName?.toLowerCase();
      const isEditable =
        tag === 'input' ||
        tag === 'textarea' ||
        tag === 'select' ||
        target?.isContentEditable;
      if (isEditable) return;
      // Modifier ignorieren
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      const k = e.key.toLowerCase();
      const match = SICHTUNG.find((s) => s.shortcut === k);
      if (match) {
        e.preventDefault();
        handleQuick(match.key);
        return;
      }
      if (k === 'n') {
        e.preventDefault();
        onOpenDialog?.();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [disabled, handleQuick, onOpenDialog]);

  const toneClass = {
    red: 'bg-status-red text-status-red-fg hover:bg-status-red/90',
    yellow: 'bg-status-yellow text-status-yellow-fg hover:bg-status-yellow/90',
    green: 'bg-status-green text-status-green-fg hover:bg-status-green/90',
    gray: 'bg-status-gray text-status-gray-fg hover:bg-status-gray/90',
  };

  return (
    <div
      data-testid="quick-entry-bar"
      className={cn(
        'sticky bottom-0 z-20 flex items-center gap-3 border-t border-border bg-surface-sunken/95 px-4 py-3 backdrop-blur',
        className,
      )}
    >
      <div className="flex items-center gap-2 text-caption text-muted-foreground">
        <Keyboard className="h-3.5 w-3.5" />
        <span className="font-medium text-foreground">Schnellerfassung</span>
        <span className="hidden md:inline">
          · Tippe eine Sichtung fuer sofortige Anlage
        </span>
      </div>

      <div className="flex flex-1 items-center justify-center gap-2">
        {SICHTUNG.map((s) => (
          <button
            key={s.key}
            type="button"
            disabled={disabled || busyKey !== null}
            onClick={() => handleQuick(s.key)}
            data-testid={`quick-sichtung-${s.key}`}
            title={`${s.label} – ${s.hint} (Taste ${s.shortcut})`}
            className={cn(
              'relative inline-flex h-12 w-16 flex-col items-center justify-center rounded-md font-semibold shadow-sm transition-all active:scale-[0.97] disabled:opacity-60',
              'els-focus-ring',
              toneClass[s.tone],
            )}
          >
            <span className="font-mono text-display leading-none">{s.key}</span>
            <span className="text-[0.65rem] uppercase opacity-80">
              {s.hint.split(' ')[0]}
            </span>
            <kbd className="absolute -top-1.5 -right-1.5 inline-flex h-4 w-4 items-center justify-center rounded-sm border border-border bg-background text-[0.6rem] font-mono text-foreground">
              {s.shortcut}
            </kbd>
            {busyKey === s.key && (
              <span className="absolute inset-0 rounded-md bg-black/20 animate-pulse" />
            )}
          </button>
        ))}


        <div className="mx-1 h-10 w-px bg-border" />
        
        <button
            type="button"
            disabled={disabled || busyKey !== null}
            onClick={() => setDummyPromptOpen(true)}
            data-testid="quick-dummy"
            title="Dummy-Patient ohne Sichtung anlegen"
            className={cn(
              'relative inline-flex h-12 flex-col items-center justify-center rounded-md border border-border px-3 font-semibold shadow-sm transition-all active:scale-[0.97] disabled:opacity-60',
              'els-focus-ring hover:bg-surface-raised'
            )}
          >
            <span className="font-mono text-heading leading-none">DUMMY</span>
            <span className="text-[0.65rem] uppercase opacity-80 mt-1">ohne Sichtung</span>
            {busyKey === "dummy" && (
              <span className="absolute inset-0 rounded-md bg-black/20 animate-pulse" />
            )}
        </button>
        <div className="mx-1 h-10 w-px bg-border" />

        <Button
          onClick={onOpenDialog}
          disabled={disabled}
          data-testid="quick-open-dialog"
          variant="outline"
          className="h-12"
        >
          <Plus className="h-4 w-4" />
          <span className="hidden sm:inline">Detail-Erfassung</span>
          <kbd className="ml-1 hidden sm:inline-flex h-4 w-4 items-center justify-center rounded-sm border border-border bg-background text-[0.6rem] font-mono">
            N
          </kbd>
        </Button>
      </div>

      <Dialog open={dummyPromptOpen} onOpenChange={setDummyPromptOpen}>
        <DialogContent className="sm:max-w-sm" data-testid="dummy-prompt-dialog">
          <DialogHeader>
            <DialogTitle>Dummy-Patient anlegen</DialogTitle>
            <DialogDescription>
              Wer meldet diesen Patienten? (z.B. "Streife 1")
            </DialogDescription>
          </DialogHeader>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              if (dummyResource) {
                setBusyKey("dummy");
                setDummyPromptOpen(false);
                try {
                  if (onQuickCreate) {
                    const selectedRes = resources.find(r => r.id === dummyResource);
                    const payload = {
                      isDummy: true,
                      behandlung_ressource_id: dummyResource,
                      created_by_resource: selectedRes ? selectedRes.name : dummyResource
                    };
                    await onQuickCreate(payload);
                  }
                } catch (err) {
                  console.error(err);
                } finally {
                  setBusyKey(null);
                  setDummyResource("");
                }
              }
            }}
            className="space-y-4"
          >
            <div>
              <Label>Erzeugende Ressource</Label>
              {loadingResources ? (
                 <div className="flex items-center gap-2 mt-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Ressourcen werden geladen...</div>
              ) : (
                <Select value={dummyResource} onValueChange={setDummyResource} required>
                    <SelectTrigger className="mt-1">
                        <SelectValue placeholder="Ressource wählen" />
                    </SelectTrigger>
                    <SelectContent>
                        {resources.map((r) => (
                            <SelectItem key={r.id} value={r.id}>{r.name}</SelectItem>
                        ))}
                    </SelectContent>
                </Select>
              )}
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setDummyPromptOpen(false)}>
                Abbrechen
              </Button>
              <Button type="submit" disabled={!dummyResource || loadingResources}>
                Anlegen
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

    </div>
  );
}
