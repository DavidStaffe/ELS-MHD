import * as React from 'react';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';

const INTERVALS = [5, 10, 20, 30, 60, 120, 300];

export default function EinstellungenPage() {
  const [password, setPassword] = React.useState('');
  const [settings, setSettings] = React.useState(null);
  const [apiKey, setApiKey] = React.useState('');
  const [interval, setIntervalValue] = React.useState(30);
  const [busy, setBusy] = React.useState(false);
  const headers = React.useMemo(() => ({ 'X-ELS-Admin-Password': password }), [password]);
  const load = async () => {
    setBusy(true);
    try {
      const { data } = await api.get('/settings/divera', { headers });
      setSettings(data);
      setIntervalValue(data.poll_interval_seconds);
    } catch (error) {
      toast.error(error?.response?.data?.detail || 'Admin-Zugang fehlgeschlagen');
    } finally { setBusy(false); }
  };
  const testKey = async () => {
    if (!apiKey.trim()) return toast.error('Zuerst neuen API-Key eingeben');
    setBusy(true);
    try {
      const { data } = await api.post('/settings/divera/test', { api_key: apiKey.trim() }, { headers });
      toast.success(`Verbindung erfolgreich · ${data.vehicles_total} Fahrzeuge`);
    } catch (error) { toast.error(error?.response?.data?.detail || 'Verbindung fehlgeschlagen'); }
    finally { setBusy(false); }
  };
  const save = async () => {
    setBusy(true);
    try {
      const payload = { interval_seconds: interval };
      if (apiKey.trim()) payload.api_key = apiKey.trim();
      const { data } = await api.patch('/settings/divera', payload, { headers });
      setSettings(data);
      setApiKey('');
      toast.success('Einstellungen sofort übernommen');
    } catch (error) { toast.error(error?.response?.data?.detail || 'Speichern fehlgeschlagen'); }
    finally { setBusy(false); }
  };
  return (
    <div className="mx-auto max-w-3xl px-6 py-6 space-y-6">
      <div><h1 className="text-2xl font-semibold">Einstellungen</h1>
        <p className="text-muted-foreground text-sm">Installationsweite Konfiguration, unabhängig vom ausgewählten Einsatz.</p></div>
      <section className="els-surface p-5 space-y-4">
        <h2 className="font-semibold text-lg">Administratorzugang</h2>
        <p className="text-sm text-muted-foreground">Zurzeit separates Admin-Passwort; Benutzer-Login und Rollenvergabe werden später definiert.</p>
        <div className="space-y-1"><Label htmlFor="els-admin-pass">Administrator-Passwort</Label>
          <Input id="els-admin-pass" type="password" autoComplete="off" value={password} onChange={e=>setPassword(e.target.value)} /></div>
        <Button type="button" onClick={load} disabled={busy || !password}>Einstellungen entsperren</Button>
      </section>
      {settings && <section className="els-surface p-5 space-y-5">
        <h2 className="font-semibold text-lg">DIVERA 24/7</h2>
        <p className="text-sm text-muted-foreground">Ein zentraler Schlüssel und ein gemeinsamer Abruf für alle verbundenen Einsätze.</p>
        <p className="text-sm">API-Key: <strong>{settings.configured ? 'Hinterlegt' : 'Nicht eingerichtet'}</strong></p>
        <div className="space-y-1"><Label htmlFor="divera-new-key">Neuen API-Key hinterlegen</Label>
          <Input id="divera-new-key" type="password" autoComplete="new-password" value={apiKey}
            onChange={e=>setApiKey(e.target.value)} placeholder="Leer lassen, um bisherigen Key beizubehalten" />
          <p className="text-xs text-muted-foreground">Der bestehende Key wird niemals im Browser angezeigt.</p></div>
        <Button variant="outline" type="button" onClick={testKey} disabled={busy || !apiKey.trim()}>Neuen Key testen</Button>
        <div className="space-y-1"><Label htmlFor="divera-interval">Abrufintervall</Label>
          <select id="divera-interval" className="flex w-full rounded-md border border-input bg-background px-3 py-2"
            value={interval} onChange={e=>setIntervalValue(Number(e.target.value))}>
            {INTERVALS.map(s=><option key={s} value={s}>{s < 60 ? `${s} Sekunden` : `${s / 60} Minute(n)`}</option>)}
          </select></div>
        <Button type="button" onClick={save} disabled={busy}>Speichern und sofort übernehmen</Button>
      </section>}
    </div>
  );
}
