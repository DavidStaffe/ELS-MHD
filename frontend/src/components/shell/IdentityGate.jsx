import * as React from 'react';
import { api, API_BASE } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

export function IdentityGate({ session, refresh, logout }) {
  const [username, setUsername] = React.useState('');
  const [password, setPassword] = React.useState('');
  const [code, setCode] = React.useState('');
  const [name, setName] = React.useState('');
  const [mode, setMode] = React.useState('login');
  const [result, setResult] = React.useState(null);
  const [error, setError] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const locked = session?.locked;
  const change = session?.user?.must_change_password;
  const [newEvents, setNewEvents] = React.useState(false);
  React.useEffect(() => {
    if (!locked) return undefined;
    const stream = new EventSource(`${API_BASE}/auth/events`, { withCredentials: true });
    stream.addEventListener('changed', () => setNewEvents(true));
    return () => stream.close();
  }, [locked]);
  const submit = async (event) => {
    event.preventDefault(); setBusy(true); setError('');
    try {
      if (locked) { await api.post('/auth/unlock', { password }); sessionStorage.removeItem('els-workstation-locked'); }
      else if (change) await api.post('/auth/password', { password });
      else if (mode === 'setup' || mode === 'recover') {
        const { data } = await api.post('/auth/' + mode, { username, ...(mode === 'setup' ? { display_name: name } : {}), code });
        setResult(data); setMode('login');
      } else await api.post('/auth/login', { username, password });
      await refresh();
    } catch (e) { setError(typeof e?.response?.data?.detail === 'string' ? e.response.data.detail : 'Aktion fehlgeschlagen.'); }
    finally { setPassword(''); setCode(''); setBusy(false); }
  };
  return <main className="min-h-screen flex items-center justify-center bg-background p-6">
    <section className="els-surface max-w-md w-full p-6 space-y-4">
      <h1 className="text-heading">{locked ? 'Arbeitsplatz gesperrt' : change ? 'Neues Passwort festlegen' : mode === 'setup' ? 'Einmalige Ersteinrichtung' : mode === 'recover' ? 'Administrator wiederherstellen' : 'ELS-MHD Anmeldung'}</h1>
      {locked && <p>Zum Entsperren erneut authentifizieren.</p>}
      {session?.notice && <p role="alert">{session.notice}</p>}
      {locked && newEvents && <p role="status">Neue Ereignisse vorhanden</p>}
      {result && <div className="border border-primary p-3" role="status"><p>Jetzt sicher verwahren. Diese Angaben werden nur einmal angezeigt.</p><p>Erstpasswort: <code>{result.initial_password}</code></p><p>Recovery-Code: <code>{result.recovery_code}</code></p><Button onClick={() => setResult(null)}>Sicher verwahrt</Button></div>}
      <form onSubmit={submit} className="space-y-3">
        {!locked && !change && <label className="block">Benutzername<Input value={username} onChange={e => setUsername(e.target.value)} autoComplete="username" required /></label>}
        {!locked && !change && mode === 'setup' && <label className="block">Klarname<Input value={name} onChange={e => setName(e.target.value)} required /></label>}
        {!locked && !change && mode !== 'login' ? <label className="block">{mode === 'setup' ? 'Setup-Code vom Betreiber' : 'Recovery-Code'}<Input type="password" value={code} onChange={e => setCode(e.target.value)} required /></label> : <label className="block">{change ? 'Neues Passwort (mindestens 12 Zeichen)' : 'Passwort'}<Input type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete={change ? 'new-password' : 'current-password'} minLength={change ? 12 : 1} required /></label>}
        {error && <p role="alert">{error}</p>}
        <Button disabled={busy} type="submit">{locked ? 'Entsperren' : change ? 'Passwort ändern' : mode === 'login' ? 'Anmelden' : 'Bestätigen'}</Button>
      </form>
      {session && (locked || change) ? <Button variant="outline" onClick={logout}>Abmelden / Benutzer wechseln</Button> : <div className="flex flex-wrap gap-2">{['login', 'setup', 'recover'].map(m => <Button key={m} variant="ghost" onClick={() => { setMode(m); setError(''); }}>{m === 'login' ? 'Anmeldung' : m === 'setup' ? 'Ersteinrichtung' : 'Wiederherstellung'}</Button>)}</div>}
    </section>
  </main>;
}
