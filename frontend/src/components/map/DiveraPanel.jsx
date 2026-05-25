import * as React from 'react';
import {
  getDiveraStatus,
  startDiveraPolling,
  stopDiveraPolling,
  diveraSyncNow,
  getDiveraConfigured,
} from '@/lib/api';
import { Button } from '@/components/ui/button';
import { StatusBadge } from '@/components/primitives';
import { Switch } from '@/components/ui/switch';
import {
  RefreshCw,
  Activity,
  RadioTower,
  AlertTriangle,
  CheckCircle2,
} from 'lucide-react';
import { toast } from 'sonner';

/**
 * DiveraPanel – kompakte Status- & Start/Stop-Steuerung pro Incident.
 * Props:
 *   incidentId
 *   disabled: bool (z.B. fuer archivierte Incidents)
 *   onChange?: () => void   – nach Sync aufgerufen, damit Eltern-State refresht
 */
export function DiveraPanel({ incidentId, disabled = false, onChange }) {
  const [configured, setConfigured] = React.useState(null);
  const [status, setStatus] = React.useState(null);
  const [busy, setBusy] = React.useState(false);

  const load = React.useCallback(async () => {
    if (!incidentId) return;
    try {
      const cfg = await getDiveraConfigured();
      setConfigured(cfg.configured);
      const s = await getDiveraStatus(incidentId);
      setStatus(s);
    } catch (e) {
      console.warn('Divera-Status nicht ladbar', e);
    }
  }, [incidentId]);

  React.useEffect(() => {
    load();
    // Poll status every 10s so UI shows fresh last_poll_at
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, [load]);

  if (configured === false) {
    return (
      <div
        className="els-surface p-3 text-caption text-muted-foreground"
        data-testid="divera-panel-not-configured"
      >
        <div className="flex items-center gap-2 mb-1">
          <RadioTower className="h-3.5 w-3.5" />
          <span className="text-foreground font-medium">Divera 24/7</span>
        </div>
        Kein API-Key konfiguriert. Setze <code className="font-mono">DIVERA_API_KEY</code>{' '}
        in der Backend-.env, um FMS-Status automatisch zu pullen.
      </div>
    );
  }

  if (!status) {
    return (
      <div className="els-surface p-3 text-caption text-muted-foreground" data-testid="divera-panel-loading">
        Divera-Status laedt…
      </div>
    );
  }

  const handleToggle = async (checked) => {
    if (busy || disabled) return;
    setBusy(true);
    try {
      if (checked) {
        const r = await startDiveraPolling(incidentId);
        toast.success(
          `Divera-Sync gestartet · ${r.first_sync?.matched ?? 0} Fahrzeuge aktualisiert`
        );
      } else {
        await stopDiveraPolling(incidentId);
        toast.success('Divera-Sync gestoppt');
      }
      await load();
      onChange?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Aktion fehlgeschlagen');
    } finally {
      setBusy(false);
    }
  };

  const handleSyncNow = async () => {
    if (busy || disabled) return;
    setBusy(true);
    try {
      const r = await diveraSyncNow(incidentId);
      if (r.ok) {
        toast.success(`Sync ok · ${r.matched}/${r.vehicles_total} matched`);
      } else {
        toast.error(`Sync fehlgeschlagen: ${r.error || 'unbekannt'}`);
      }
      await load();
      onChange?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Sync fehlgeschlagen');
    } finally {
      setBusy(false);
    }
  };

  const lastError = status.last_status && status.last_status.startsWith('error:');
  const lastOk = status.last_status === 'ok';

  return (
    <div className="els-surface p-3" data-testid="divera-panel">
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <RadioTower
            className={
              'h-4 w-4 shrink-0 ' +
              (status.running ? 'text-emerald-500' : 'text-muted-foreground')
            }
          />
          <div className="min-w-0">
            <div className="text-sm font-medium">Divera 24/7</div>
            <div className="text-[10px] text-muted-foreground">
              {status.linked_resources} verknuepfte Ressource(n) · Polling alle{' '}
              {status.poll_interval_seconds}s
            </div>
          </div>
        </div>
        <Switch
          checked={status.running}
          onCheckedChange={handleToggle}
          disabled={busy || disabled}
          data-testid="divera-toggle"
        />
      </div>

      <div className="flex items-center gap-2 text-caption text-muted-foreground">
        {lastOk && (
          <StatusBadge tone="green" variant="soft" size="sm">
            <CheckCircle2 className="h-3 w-3" />
            ok
          </StatusBadge>
        )}
        {lastError && (
          <StatusBadge tone="red" variant="soft" size="sm">
            <AlertTriangle className="h-3 w-3" />
            Fehler
          </StatusBadge>
        )}
        {!lastOk && !lastError && (
          <StatusBadge tone="gray" variant="soft" size="sm">
            inaktiv
          </StatusBadge>
        )}
        <span className="font-mono text-[10px] truncate">
          {status.last_poll_at
            ? new Date(status.last_poll_at).toLocaleTimeString('de-DE')
            : 'nie'}
        </span>
        {status.last_match_count !== null && status.last_match_count !== undefined && (
          <span className="text-[10px] tabular-nums">
            · {status.last_match_count} matched
          </span>
        )}
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-6 w-6 p-0 ml-auto"
          onClick={handleSyncNow}
          disabled={busy || disabled}
          title="Jetzt synchronisieren"
          data-testid="divera-sync-now"
        >
          <RefreshCw className={'h-3.5 w-3.5 ' + (busy ? 'animate-spin' : '')} />
        </Button>
      </div>
      {lastError && (
        <div className="mt-2 text-[10px] text-status-red" data-testid="divera-last-error">
          {status.last_status}
        </div>
      )}
    </div>
  );
}
