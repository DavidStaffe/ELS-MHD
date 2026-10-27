import * as React from 'react';
import { Link } from 'react-router-dom';
import { Settings, Radio, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { api } from '@/lib/api';

const INTERVALS = [5, 10, 20, 30, 60, 120, 300];
const field = 'rounded-md border border-border bg-surface px-3 py-2';
const date = (value) => value ? new Date(value).toLocaleString('de-DE') : 'Noch nie';

export default function EinstellungenPage() {
  const [info, setInfo] = React.useState(null);
  const [error, setError] = React.useState('');
  const [message, setMessage] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [token, setToken] = React.useState('');
  const [password, setPassword] = React.useState('');
  const [key, setKey] = React.useState('');
  const [keyOpen, setKeyOpen] = React.useState(false);
  const [tested, setTested] = React.useState(false);
  const [interval, setIntervalValue] = React.useState(30);

  const refresh = React.useCallback(async () => {
    try {
      const { data } = await api.get('/divera/settings');
      setInfo(data);
      return data;
    } catch {
      setError('DIVERA-Status konnte nicht geladen werden.');
    }
  }, []);
  React.useEffect(() => {
    refresh().then((data) => { if (data) setIntervalValue(data.poll_interval_seconds); });
    const timer = setInterval(refresh, 10000);
    return () => clearInterval(timer);
  }, [refresh]);
  React.useEffect(() => {
    if (!token) return undefined;
    const timer = setTimeout(() => { setToken(''); setKey(''); setTested(false); setKeyOpen(false); }, 600000);
    return () => clearTimeout(timer);
  }, [token]);

  const perform = async (operation) => {
    setBusy(true); setError(''); setMessage('');
    try { await operation(); }
    catch (e) {
      if (e?.response?.status === 401) { setToken(''); setKey(''); setKeyOpen(false); }
      const detail = e?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Aktion fehlgeschlagen. Bitte erneut versuchen.');
    } finally { setBusy(false); }
  };
  const auth = { headers: { Authorization: 'Bearer ' + token }, timeout: 60000 };
  const login = (event) => {
    event.preventDefault();
    perform(async () => {
      try {
        const { data } = await api.post('/admin/login', { password });
        setToken(data.token); setMessage('Administratorzugang für zehn Minuten freigeschaltet.');
      } finally { setPassword(''); }
    });
  };
  const logout = () => perform(async () => {
    try { await api.post('/admin/logout', {}, auth); }
    finally { setToken(''); setKey(''); setTested(false); setKeyOpen(false); }
  });
  const testKey = () => perform(async () => {
    setTested(false);
    const { data } = await api.post('/divera/settings/test', { api_key: key }, auth);
    setTested(true); setMessage('Verbindung erfolgreich · ' + data.vehicles_total + ' Fahrzeuge abrufbar.');
  });
  const saveKey = () => perform(async () => {
    await api.put('/divera/settings/key', { api_key: key }, auth);
    setKey(''); setTested(false); setKeyOpen(false);
    setMessage('API-Key geprüft, gespeichert und sofort übernommen.'); await refresh();
  });
  const saveInterval = () => perform(async () => {
    await api.put('/divera/settings/interval', { interval }, auth);
    setMessage('Intervall gespeichert und sofort übernommen.'); await refresh();
  });

  return (
    <main className="mx-auto w-full max-w-[900px] space-y-6 px-6 py-6" data-testid="settings-page">
      <div>
        <p className="text-caption uppercase tracking-wider text-muted-foreground">Systemverwaltung</p>
        <h1 className="mt-1 text-display flex items-center gap-2"><Settings className="h-6 w-6 text-primary" />Einstellungen</h1>
        <p className="mt-1 text-body text-muted-foreground">Zentrale Einstellungen für alle Einsätze dieser Installation.</p>
      </div>
      <section className="rounded-md border border-border bg-surface p-5 space-y-4">
        <h2 className="font-semibold">Administratorzugang</h2>
        {token ? <Button variant="outline" onClick={logout} disabled={busy}>Administratorsitzung beenden</Button> : (
          <form onSubmit={login} className="flex flex-wrap gap-3 items-end">
            <label className="space-y-1">Administratorpasswort
              <input className={field + ' block'} type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} disabled={busy} required />
            </label>
            <Button type="submit" disabled={busy || !password}>Anmelden</Button>
          </form>
        )}
        <p className="text-caption text-muted-foreground">Schlüssel- und Intervalländerungen benötigen den gesonderten Administratorzugang. Die im Einsatz gewählte Rolle reicht dafür nicht aus.</p>
      </section>
      {error && <p role="alert" className="text-status-red">{error}</p>}
      {message && <p role="status">{message}</p>}
      <section className="rounded-md border border-border bg-surface p-5 space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-heading font-semibold flex items-center gap-2"><Radio className="h-5 w-5" />DIVERA 24/7</h2>
          <Button variant="outline" onClick={refresh} disabled={busy}><RefreshCw className="mr-2 h-4 w-4" />Aktualisieren</Button>
        </div>
        <p>API-Key: <strong>{!info ? 'Wird geladen …' : info.configured ? 'Hinterlegt (nicht auslesbar)' : 'Nicht hinterlegt'}</strong></p>
        {info?.configuration_error && <p role="alert">{info.configuration_error}</p>}
        <p>Letzter erfolgreicher Abruf: {date(info?.last_success_at)}</p>
        <p>Letzter Schlüsseltest: {date(info?.key_verified_at)}</p>
        <p>Verbindung: {info?.error || (info?.last_success_at ? 'Letzter Abruf erfolgreich' : 'Noch kein erfolgreicher Abruf')}</p>
        {!!info?.failures && <p>Nächster Versuch: {date(info.next_at)} · {info.failures} fehlgeschlagene Abrufe</p>}
        <Button disabled={!token || busy} onClick={() => { setKey(''); setTested(false); setKeyOpen(true); }}>API-Key ändern</Button>
        <div className="border-t border-border pt-4 space-y-2">
          <label htmlFor="divera-interval" className="block font-semibold">Synchronisierungsintervall</label>
          <select id="divera-interval" className={field} disabled={!token || busy} value={interval} onChange={(e) => setIntervalValue(Number(e.target.value))}>
            {INTERVALS.map((n) => <option key={n} value={n} disabled={n === 5}>{n} Sekunden{n === 5 ? ' – noch nicht freigegeben' : ''}</option>)}
          </select>
          <Button className="ml-3" onClick={saveInterval} disabled={!token || busy || interval === info?.poll_interval_seconds}>Intervall speichern</Button>
          <p className="text-caption text-muted-foreground">Aktuell: {info?.poll_interval_seconds ?? 30} Sekunden. Standard: 30 Sekunden. 5 Sekunden bleiben bis zur Prüfung der DIVERA-Limits gesperrt.</p>
          <p className="text-caption text-muted-foreground">Ein gemeinsamer Abruf versorgt alle aktivierten Einsätze. Bei Verbindungsfehlern verlängert sich der Abstand automatisch.</p>
        </div>
      </section>
      <Dialog open={keyOpen} onOpenChange={(open) => { if (!busy) { setKeyOpen(open); setKey(''); setTested(false); } }}>
        <DialogContent>
          <DialogHeader><DialogTitle>Globalen DIVERA-Key ändern</DialogTitle><DialogDescription>Der neue Key gilt sofort für alle Einsätze. Bei fehlgeschlagener Prüfung bleibt der bisherige Key erhalten.</DialogDescription></DialogHeader>
          <label htmlFor="divera-key">Neuer API-Key</label>
          <input id="divera-key" className={field} type="password" autoComplete="off" spellCheck={false} value={key} disabled={busy} onChange={(e) => { setKey(e.target.value); setTested(false); }} />
          {error && <p role="alert">{error}</p>}
          {message && <p role="status">{message}</p>}
          <Button variant="outline" disabled={busy || !key} onClick={testKey}>Verbindung testen</Button>
          <Button disabled={busy || !tested || !key} onClick={saveKey}>Speichern und übernehmen</Button>
        </DialogContent>
      </Dialog>
      <section className="rounded-md border border-border bg-surface p-5 space-y-2">
        <h2 className="font-semibold">System & Updates</h2>
        <p className="text-body text-muted-foreground">Softwarestände, Updates und Rollback verwalten.</p>
        <Button asChild variant="outline"><Link to="/system-updates">Zur Updateverwaltung</Link></Button>
      </section>
    </main>
  );
}
