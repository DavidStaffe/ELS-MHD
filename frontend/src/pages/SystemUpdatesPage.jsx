import { Link } from 'react-router-dom';
import * as React from 'react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';

const phases = { idle: 'Bereit', queued: 'Angenommen', verify: 'Releaseprüfung', backup: 'Backup und Wartungsfenster', deploy: 'Installation', health: 'Funktionsprüfung', recover: 'Wiederherstellung', complete: 'Abgeschlossen', failed: 'Fehlgeschlagen, vorherige Version aktiv', recovery_required: 'SSH-Hilfe erforderlich' };
const busyPhases = ['queued', 'verify', 'backup', 'deploy', 'health', 'recover'];
export default function SystemUpdatesPage() {
  const [status, setStatus] = React.useState(null);
  const [release, setRelease] = React.useState(null);
  const [error, setError] = React.useState('');
  const [connectionError, setConnectionError] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [action, setAction] = React.useState('');
  const [password, setPassword] = React.useState('');
  const [updatePassword, setUpdatePassword] = React.useState('');
  const [confirmed, setConfirmed] = React.useState(false);
  const load = React.useCallback(async () => {
    try {
      const { data } = await api.get('/system/updates/status');
      setStatus(data); setConnectionError('');
    } catch {
      setConnectionError('Host/App derzeit nicht erreichbar. Während der Wartung wird automatisch erneut verbunden. Vorgang nicht erneut starten.');
    }
  }, []);
  React.useEffect(() => {
    load(); const timer = setInterval(load, 3000);
    return () => clearInterval(timer);
  }, [load]);
  const check = async () => {
    setBusy(true);
    try {
      const { data } = await api.get('/system/updates/check');
      setStatus(data); setRelease(data); setError('');
    } catch (e) { setError(typeof e?.response?.data?.detail === 'string' ? e.response.data.detail : 'Updateprüfung fehlgeschlagen.'); }
    finally { setBusy(false); }
  };
  const perform = async (event) => {
    event.preventDefault(); setBusy(true); setError('');
    let token;
    try {
      const login = await api.post('/admin/login', { password });
      token = login.data.token;
      const version = action === 'apply' ? release.available_version : status.rollback_version;
      const release_id = action === 'apply' ? release.release_id : status.rollback_id;
      const { data } = await api.post('/system/updates/' + action, { password: updatePassword, version, release_id }, { headers: { Authorization: 'Bearer ' + token } });
      setStatus(data); setAction(''); setRelease(null);
    } catch (e) {
      const detail = e?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Freigabe fehlgeschlagen. Status prüfen, bevor Sie erneut starten.');
    } finally {
      setPassword(''); setUpdatePassword(''); setConfirmed(false); setBusy(false);
      if (token) api.post('/admin/logout', {}, { headers: { Authorization: 'Bearer ' + token } }).catch(() => {});
    }
  };
  const running = busyPhases.includes(status?.state);
  return <main className="mx-auto w-full max-w-[900px] space-y-5 px-6 py-6" data-testid="system-updates-page">
    <Link to="/einstellungen" className="text-primary underline">Zurück zu den Einstellungen</Link>
    <h1 className="text-display">System & Updates</h1>
    <section className="rounded-md border border-border bg-surface p-5 space-y-4">
      <p>Installierte Version: <strong>{status?.running_version || 'Unbekannt'}</strong></p>
      <p>Freigegebene Version: <strong>{release?.available_version || 'Bitte prüfen'}</strong></p>
      <p>Rollback-Version: <strong>{status?.rollback_version || 'Kein Checkpoint'}</strong></p>
      <div role="status" aria-live="polite"><strong>{phases[status?.state] || 'Nicht eingerichtet'}</strong><p>{status?.message}</p></div>
      {running && <progress aria-label="Update läuft" />}
      {status?.operation_id && <p className="text-caption">Vorgang: {status.operation_id}</p>}
      {release?.notes && <p className="whitespace-pre-wrap">{release.notes}</p>}
      {error && <p role="alert" className="text-status-red">{error}</p>}
      {connectionError && <p role="status">{connectionError}</p>}
      {status?.last_error && <p role="alert">{status.last_error}</p>}
      <div className="flex flex-wrap gap-3">
        <Button variant="outline" onClick={check} disabled={busy || running || !status?.configured}>Auf Updates prüfen</Button>
        <Button onClick={() => { setAction('apply'); setConfirmed(false); }} disabled={busy || running || !status?.can_install || !release?.update_available}>Update installieren</Button>
        <Button variant="outline" onClick={() => { setAction('rollback'); setConfirmed(false); }} disabled={busy || running || !status?.can_rollback}>Rollback</Button>
      </div>
      {action && <form onSubmit={perform} className="space-y-3 rounded border p-4">
        <h2>{action === 'apply' ? 'Update freigeben' : 'Rollback freigeben'}</h2>
        <p>Die WebApp ist kurzzeitig nicht erreichbar. Aktive Einsätze sperren den Vorgang. Die Datenbank wird bei einem Rollback nicht zurückgesetzt.</p>
        <label className="block">Administratorpasswort<input required className="block border rounded p-2" type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} disabled={busy} /></label>
        <label className="block">Separates Updatepasswort<input required className="block border rounded p-2" type="password" autoComplete="off" value={updatePassword} onChange={e => setUpdatePassword(e.target.value)} disabled={busy} /></label>
        <label className="block"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} disabled={busy} /> Wartungsfenster und gewählte Version verbindlich bestätigen</label>
        <Button type="submit" disabled={busy || !confirmed || !password || !updatePassword}>Jetzt {action === 'apply' ? 'installieren' : 'zurücksetzen'}</Button>
        <Button type="button" variant="outline" disabled={busy} onClick={() => { setAction(''); setPassword(''); setUpdatePassword(''); setConfirmed(false); }}>Abbrechen</Button>
      </form>}
    </section>
    <p className="text-caption">Passwörter und Anmeldung werden nicht im Browser gespeichert. Bei unterbrochener Verbindung wird der Zustand automatisch neu geladen.</p>
  </main>;
}
