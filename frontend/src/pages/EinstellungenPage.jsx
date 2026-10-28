import * as React from 'react';
import { Link } from 'react-router-dom';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useRole } from '@/context/RoleContext';

export default function EinstellungenPage() {
 const { can } = useRole();
 const [info, setInfo] = React.useState(null);
 const [key, setKey] = React.useState('');
 const [interval, setIntervalValue] = React.useState(30);
 const [tested, setTested] = React.useState(false);
 const [message, setMessage] = React.useState('');
 const [busy, setBusy] = React.useState(false);
 const load = React.useCallback(async () => {
   try { const { data } = await api.get('/divera/settings'); setInfo(data); setIntervalValue(data.poll_interval_seconds); }
   catch { setMessage('Einstellungen konnten nicht geladen werden.'); }
 }, []);
 React.useEffect(() => { if (can('settings.manage')) load(); }, [load, can]);
 const perform = async (operation) => {
   setBusy(true); setMessage('');
   try { await operation(); await load(); }
   catch (e) { setMessage(typeof e?.response?.data?.detail === 'string' ? e.response.data.detail : 'Aktion fehlgeschlagen.'); }
   finally { setBusy(false); }
 };
 return <main className="mx-auto max-w-[900px] p-6 space-y-6" data-testid="settings-page">
   <h1 className="text-display">Einstellungen</h1>
   <section className="els-surface p-5 space-y-3"><h2 className="text-heading">Verwaltung</h2>
     {can('users.manage') && <Button asChild variant="outline"><Link to="/benutzer">Benutzer und globale Rechte</Link></Button>}
     <Button asChild variant="outline"><Link to="/einsatzrechte">Einsatzrollen und Archivverwaltung</Link></Button>
     {can('settings.manage') && <Button asChild variant="outline"><Link to="/system-updates">System & Updates</Link></Button>}
   </section>
   {message && <p role="status">{message}</p>}
   {can('settings.manage') && <section className="els-surface p-5 space-y-4"><h2 className="text-heading">DIVERA 24/7</h2>
     <p>API-Key: {info?.configured ? 'Hinterlegt (nicht auslesbar)' : 'Nicht hinterlegt'}</p>
     <p>Letzter erfolgreicher Abruf: {info?.last_success_at ? new Date(info.last_success_at).toLocaleString('de-DE') : 'Noch nie'}</p>
     <p>{info?.configuration_error || info?.error}</p>
     <label className="block">Neuer API-Key<Input type="password" autoComplete="off" value={key} onChange={e => { setKey(e.target.value); setTested(false); }} /></label>
     <Button disabled={busy || !key} onClick={() => perform(async () => { await api.post('/divera/settings/test', {api_key:key}); setTested(true); setMessage('Verbindung erfolgreich.'); })}>Verbindung testen</Button>
     <Button disabled={busy || !tested} onClick={() => perform(async () => { await api.put('/divera/settings/key', {api_key:key}); setKey(''); setTested(false); setMessage('Key geprüft und übernommen.'); })}>Key speichern</Button>
     <label className="block">Abrufintervall<select className="block bg-background border rounded p-2" value={interval} onChange={e => setIntervalValue(Number(e.target.value))}>
       {[5,10,20,30,60,120,300].map(n => <option key={n} value={n} disabled={n===5}>{n} Sekunden{n===5?' – gesperrt':''}</option>)}
     </select></label>
     <Button disabled={busy || interval===info?.poll_interval_seconds} onClick={() => perform(async () => { await api.put('/divera/settings/interval', {interval}); setMessage('Intervall übernommen.'); })}>Intervall speichern</Button>
   </section>}
 </main>;
}
