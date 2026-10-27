import * as React from 'react';
import { RefreshCw, ShieldAlert, RotateCcw, Download, Lock, Server } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';

export default function SystemUpdatesPage() {
  const [status, setStatus] = React.useState(null);
  const [error, setError] = React.useState('');
  const [loading, setLoading] = React.useState(true);
  const [checking, setChecking] = React.useState(false);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/system/updates/status');
      setStatus(data);
      setError('');
    } catch {
      setStatus(null);
      setError('Systemstatus derzeit nicht verfügbar.');
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { load(); }, [load]);

  const check = async () => {
    setChecking(true);
    try {
      const { data } = await api.get('/system/updates/check');
      setStatus(data);
      setError('');
    } catch (e) {
      setError(e?.response?.data?.detail || 'Updateprüfung fehlgeschlagen.');
    } finally {
      setChecking(false);
    }
  };

  const ready = status?.configured === true;
  return (
    <main className="mx-auto w-full max-w-[900px] space-y-5 px-6 py-6" data-testid="system-updates-page">
      <div>
        <p className="text-caption uppercase tracking-wider text-muted-foreground">Einstellungen</p>
        <h1 className="mt-1 text-display flex items-center gap-2"><Server className="h-6 w-6 text-primary" />System & Updates</h1>
        <p className="mt-2 text-body text-muted-foreground">Softwareversion prüfen, Updates verwalten und bei Problemen zur vorherigen Version zurückkehren.</p>
      </div>
      <section className="rounded-md border border-border bg-surface p-5 space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="font-semibold text-heading">Updateverwaltung</h2>
          <Button variant="outline" onClick={load} disabled={loading}>
            <RefreshCw className="mr-2 h-4 w-4" />Status aktualisieren
          </Button>
        </div>
        <div className="text-body">
          <p>Installierte Version: <span className="font-mono">{status?.running_version || 'Noch nicht ermittelbar'}</span></p>
          <p>Verfügbare Version: <span className="font-mono">{status?.available_version || 'Unbekannt'}</span></p>
        </div>
        {!ready && (
          <div className="rounded-md border border-amber-400/40 bg-amber-500/10 p-3 flex gap-2" role="status">
            <ShieldAlert className="h-5 w-5 shrink-0" />
            <span>{status?.message || 'Updateverwaltung ist noch nicht eingerichtet. Installation und Rollback bleiben gesperrt.'}</span>
          </div>
        )}
        {error && <p role="alert" className="text-status-red">{error}</p>}
        <div className="flex flex-wrap gap-3">
          <Button variant="outline" onClick={check} disabled={!ready || checking || loading}>
            <RefreshCw className="mr-2 h-4 w-4" />{checking ? 'Prüfe …' : 'Auf Updates prüfen'}
          </Button>
          <Button disabled title="Erst nach Einrichtung des geschützten Update-Dienstes verfügbar">
            <Lock className="mr-2 h-4 w-4" /><Download className="mr-2 h-4 w-4" />Update installieren
          </Button>
          <Button variant="outline" disabled title="Erst nach Einrichtung des geschützten Update-Dienstes verfügbar">
            <Lock className="mr-2 h-4 w-4" /><RotateCcw className="mr-2 h-4 w-4" />Rollback
          </Button>
        </div>
      </section>
      <p className="text-caption text-muted-foreground">
        Updates und Rollbacks benötigen eine gesonderte Administratorfreigabe. Ein laufender Einsatz darf nicht versehentlich unterbrochen werden.
      </p>
    </main>
  );
}
