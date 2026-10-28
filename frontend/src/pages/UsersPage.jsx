import * as React from 'react';
import { api } from '@/lib/api';
import { useRole } from '@/context/RoleContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

const empty = {username:'',display_name:'',permissions:[],eligible:[],admin:false};
export default function UsersPage() {
 const { can, user } = useRole();
 const [users,setUsers] = React.useState([]);
 const [caps,setCaps] = React.useState({permissions:[],eligible:[]});
 const [form,setForm] = React.useState(empty);
 const [selected,setSelected] = React.useState(null);
 const [secret,setSecret] = React.useState('');
 const [error,setError] = React.useState('');
 const [reason,setReason] = React.useState('');
 const [emergency,setEmergency] = React.useState(false);
 const [busy,setBusy] = React.useState(false);
 const load = React.useCallback(async () => {
   const [a,b] = await Promise.all([api.get('/auth/users'),api.get('/auth/capabilities')]);
   setUsers(a.data); setCaps(b.data);
 },[]);
 React.useEffect(() => { if (can('users.manage')) load().catch(() => setError('Benutzerliste konnte nicht geladen werden.')); },[can,load]);
 const perform = async (fn) => {setBusy(true);setError('');setSecret('');try { await fn();await load(); }catch(e){setError(typeof e?.response?.data?.detail==='string'?e.response.data.detail:'Aktion abgelehnt. Führungsfunktionen vorher übergeben; letzten Administrator aktiv lassen.');}finally{setBusy(false);}};
 const toggle = (key,value) => setForm(f => ({...f,[key]: f[key].includes(value)?f[key].filter(v=>v!==value):[...f[key],value]}));
 if(!can('users.manage')) return <main className="p-6">Keine Berechtigung.</main>;
 return <main className="max-w-[1100px] mx-auto p-6 space-y-5"><h1 className="text-display">Benutzerverwaltung</h1>
  {error&&<p role="alert">{error}</p>}{secret&&<section className="els-surface p-4" role="status"><p>Einmaliges Erstpasswort sicher weitergeben. Bei Anmeldung ist ein Wechsel erforderlich.</p><code>{secret}</code><Button onClick={()=>setSecret('')}>Sicher weitergegeben</Button></section>}
  <section className="els-surface p-5 space-y-3"><h2 className="text-heading">Konten</h2><select className="bg-background border p-2 w-full" value={selected?.id||''} onChange={e=>{const u=users.find(x=>x.id===e.target.value);setSelected(u||null);setForm(u?{...u}:empty);setSecret('');}}><option value="">Neues Konto</option>{users.map(u=><option key={u.id} value={u.id}>{u.display_name} ({u.username}) – {u.active?'aktiv':'deaktiviert'}</option>)}</select>
   <form className="space-y-3" onSubmit={e=>{e.preventDefault();perform(async()=>{if(selected){await api.put('/auth/users/'+selected.id,{display_name:form.display_name,permissions:form.permissions,eligible:form.eligible});}else{const {data}=await api.post('/auth/users',form);setSecret(data.initial_password + (data.recovery_code ? " · Recovery-Code: " + data.recovery_code : ""));}});}}>
    <label className="block">Benutzername<Input required disabled={!!selected} value={form.username} onChange={e=>setForm({...form,username:e.target.value})}/></label>
    <label className="block">Klarname<Input required value={form.display_name} onChange={e=>setForm({...form,display_name:e.target.value})}/></label>
    {user.admin&&<><h3>Globale Einzelberechtigungen</h3><div className="grid md:grid-cols-2 gap-2">{caps.permissions.map(p=><label key={p}><input type="checkbox" checked={form.permissions.includes(p)} onChange={()=>toggle('permissions',p)}/> {p}</label>)}</div>
    <h3>Eignungsfreigaben (allein kein Datenzugriff)</h3><div className="flex flex-wrap gap-4">{caps.eligible.map(p=><label key={p}><input type="checkbox" checked={form.eligible.includes(p)} onChange={()=>toggle('eligible',p)}/> {p}</label>)}</div>
    {!selected&&<label className="block"><input type="checkbox" checked={form.admin} onChange={e=>setForm({...form,admin:e.target.checked})}/> Administrator (keine automatischen operativen Leserechte)</label>}</>}
    <Button disabled={busy||!user.admin}>{selected?'Änderungen speichern':'Konto anlegen'}</Button>
   </form>
   {selected&&<div className="border-t pt-4 space-y-3"><Button disabled={busy} variant="outline" onClick={()=>perform(async()=>{const {data}=await api.post('/auth/users/'+selected.id+'/reset');setSecret(data.initial_password + (data.recovery_code ? " · Recovery-Code: " + data.recovery_code : ""));})}>Erstpasswort neu erzeugen</Button>
    <label className="block">Begründung für Sperrung<Input value={reason} onChange={e=>setReason(e.target.value)}/></label><label className="block"><input type="checkbox" checked={emergency} onChange={e=>setEmergency(e.target.checked)}/> Sicherheitsnotfallsperre sofort; offene Führungsübergaben müssen zeitnah erfolgen</label>
    <Button disabled={busy||reason.trim().length<3||!selected.active} variant="destructive" onClick={()=>perform(async()=>{await api.post('/auth/users/'+selected.id+'/deactivate',{reason,emergency});setSelected(null);setForm(empty);})}>Konto deaktivieren und Sessions widerrufen</Button>
    {!selected.active&&<Button disabled={busy||reason.trim().length<3} onClick={()=>perform(async()=>{await api.post('/auth/users/'+selected.id+'/activate',{reason});setSelected(null);setForm(empty);})}>Konto nach Rollenprüfung aktivieren</Button>}
   </div>}
  </section>
 </main>;
}
