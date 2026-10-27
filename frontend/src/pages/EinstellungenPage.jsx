import * as React from 'react';
import { Link } from 'react-router-dom';
import { Settings, Radio, RefreshCw, Lock, KeyRound } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';

const INTERVALS = [5, 10, 20, 30, 60, 120, 300];

export default function EinstellungenPage() {
  const [info, setInfo] = React.useState(null);
  const [error, setError] = React.useState('');
  const [loading, setLoading] = React.useState(true);

  const refresh = React.useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/divera/configured');
      setInfo(data);
      setError('');
    } catch {
      setError('DIVERA-Konfiguration konnte nicht geladen werden.');
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { refresh(); }, [refresh]);

  return (
    <main className="mx-auto w-full max-w-[900px] space-y-6 px-6 py-6" data-testid="settings-page">
      <div>
        <p className="text-caption uppercase tracking-wider text-muted-foreground">Systemverwaltung</p>
        <h1 className="mt-1 text-display flex items-center gap-2"><Settings className="h-6 w-6 text-primary" />Einstellungen</h1>
        <p className="mt-1 text-body text-muted-foreground">Zentrale Einstellungen dieser ELS-MHD-Installation – unabhängig vom gewählten Incident.</p>
      </div>

      <section className="rounded-md border border-border bg-surface p-5 space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-heading font-semibold flex items-center gap-2"><Radio className="h-5 w-5" /> DIVERA 24/7</h2>
          <Button variant="outline" onClick={refresh} disabled={loading}><RefreshCw className="mr-2 h-4 w-4" />Aktualisieren</Button>
        </div>
        {error && <p role="alert" className="text-status-red">{error}</p>}
        <p>API-Key: <strong>{loading ? 'Wird geladen …' : info?.configured ? 'Hinterlegt (nicht auslesbar)' : 'Nicht hinterlegt'}</strong></p>
        <p className="text-body text-muted-foreground">Ein zentraler API-Key gilt für alle Incidents. Sein Wert darf niemals wieder in der Oberfläche angezeigt werden.</p>
        <div className="flex flex-wrap items-center gap-3">
          <Button disabled title="Erst mit serverseitiger Administratoranmeldung möglich"><Lock className="mr-2 h-4 w-4" /><KeyRound className="mr-2 h-4 w-4" />API-Key ändern</Button>
          <p className="text-caption text-muted-foreground">Verbindungstest und Schlüsselwechsel werden nach Einrichtung des sicheren Administratorzugangs aktiviert.</p>
        </div>
        <div className="border-t border-border pt-4 space-y-2">
          <label htmlFor="divera-interval" className="block font-semibold">Synchronisierungsintervall</label>
          <select id="divera-interval" className="rounded-md border border-border bg-surface px-3 py-2" disabled value={info?.poll_interval_seconds ?? 30} onChange={() => {}}>
            {INTERVALS.map((n) => <option key={n} value={n}>{n} Sekunden</option>)}
          </select>
          <p className="text-caption text-muted-foreground">Vorgesehen: 5, 10, 20, 30, 60, 120 und 300 Sekunden. Standard 30 Sekunden. Änderungen sind erst nach Anbindung der zentralen Polling-Steuerung möglich. Für 5 Sekunden ist zuvor die zulässige DIVERA-Abruffrequenz zu klären.</p>
        </div>
        <div className="rounded-md border border-border bg-surface-sunken p-3 text-body" role="status">
          Konfiguration derzeit nur lesbar. Die bestehende DIVERA-Synchronisierung wird nicht verändert.
        </div>
      </section>

      <section className="rounded-md border border-border bg-surface p-5 space-y-2">
        <h2 className="font-semibold">System & Updates</h2>
        <p className="text-body text-muted-foreground">Softwarestände prüfen, Updates installieren und Rollback verwalten.</p>
        <Button asChild variant="outline"><Link to="/system-updates">Zur Updateverwaltung</Link></Button>
      </section>
    </main>
  );
}
