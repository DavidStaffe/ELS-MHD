import * as React from 'react';
import { api } from '@/lib/api';
import { useIncidents } from '@/context/IncidentContext';
import { useRole } from '@/context/RoleContext';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { ArchiveCorrectionPanel } from '@/components/incidents/ArchiveCorrectionPanel';

export default function GovernancePage() {
 const { incidents, activeId, refresh } = useIncidents();
 const { user, refresh:refreshIdentity } = useRole();
 const [catalog,setCatalog] = React.useState([]);
 const [incidentId,setIncidentId] = React.useState(activeId||'');
 const [candidates,setCandidates] = React.useState([]);
 const [target,setTarget] = React.useState('');
 const [role,setRole] = React.useState('AL');
 const [section,setSection] = React.useState('');
 const [sections,setSections] = React.useState([]);
 const [resources,setResources] = React.useState([]);
 const [resource,setResource] = React.useState('');
 const [support,setSupport] = React.useState('EL');
 const [reason,setReason] = React.useState('');
 const [days,setDays] = React.useState(30);
 const [grantTarget,setGrantTarget] = React.useState('');
 const [accounts,setAccounts] = React.useState([]);
 const [message,setMessage] = React.useState('');
 const [busy,setBusy] = React.useState(false);
 const mayManageArchive = user.admin||user.permissions.includes('archives.manage');
 React.useEffect(()=>{if(mayManageArchive) api.get('/archive-catalog').then(r=>setCatalog(r.data)).catch(()=>{});},[mayManageArchive]);
 React.useEffect(()=>{
   if(!incidentId)return;
   setCandidates([]);setSections([]);setResources([]);
   api.get(`/incidents/${incidentId}/role-candidates`).then(r=>setCandidates(r.data)).catch(()=>{});
   api.get(`/incidents/${incidentId}/abschnitte`).then(r=>setSections(r.data)).catch(()=>{});
   api.get(`/incidents/${incidentId}/resources`).then(r=>setResources(r.data)).catch(()=>{});
 },[incidentId]);
 React.useEffect(()=>{if(mayManageArchive)api.get('/archive-candidates').then(r=>setAccounts(r.data)).catch(()=>{});},[mayManageArchive]);
 const perform=async(fn)=>{setBusy(true);setMessage('');try{await fn();setMessage('Änderung protokolliert.');await refresh();await refreshIdentity();}catch(e){setMessage(typeof e?.response?.data?.detail==='string'?e.response.data.detail:'Änderung abgelehnt. Berechtigungen, Eignung, Besetzungsgrenzen und Zuordnung prüfen.');}finally{setBusy(false);}};
 const entries=Array.from(new Map([...incidents,...catalog].map(i=>[i.id,i])).values());
 const selected=entries.find(i=>i.id===incidentId);
 return <main className="max-w-[1000px] mx-auto p-6 space-y-5"><h1 className="text-display">Einsatzrollen und Archivverwaltung</h1>
  <label className="block">Einsatz<select className="block w-full border bg-background p-2 rounded" value={incidentId} onChange={e=>setIncidentId(e.target.value)}><option value="">Einsatz wählen</option>{entries.map(i=><option key={i.id} value={i.id}>{i.name} – {i.status}</option>)}</select></label>
  <label className="block">Verpflichtende Begründung<Input value={reason} onChange={e=>setReason(e.target.value)} minLength={3}/></label>
  {message&&<p role="status">{message}</p>}
  {!!candidates.length&&selected?.status!=='abgeschlossen'&&<section className="els-surface p-5 space-y-3"><h2 className="text-heading">Einsatzrolle zuweisen / wechseln / aufheben</h2>
   <label className="block">Person<select className="block bg-background border p-2" value={target} onChange={e=>setTarget(e.target.value)}><option value="">Person wählen</option>{candidates.map(u=><option key={u.id} value={u.id}>{u.display_name} ({u.eligible.join(', ')||'Helfer'})</option>)}</select></label>
   <label className="block">Rolle<select className="block bg-background border p-2" value={role} onChange={e=>setRole(e.target.value)}>{['EL','FueAss','AL','Dokumentar','Helfer',''].map(r=><option key={r} value={r}>{r||'Aktive Rolle aufheben'}</option>)}</select></label>
   {['AL','FueAss'].includes(role)&&<label className="block">Abschnitt<select className="block bg-background border p-2" value={section} onChange={e=>setSection(e.target.value)}><option value="">Zentrale EL</option>{sections.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label>}
   {role==='FueAss'&&<label className="block">Unterstützung<select className="block bg-background border p-2" value={support} onChange={e=>setSupport(e.target.value)}><option value="EL">EL</option><option value="AL">AL des gewählten Abschnitts</option></select></label>}
   {role==='Helfer'&&<label className="block">Ressource<select className="block bg-background border p-2" value={resource} onChange={e=>setResource(e.target.value)}><option value="">Ressource wählen</option>{resources.map(r=><option key={r.id} value={r.id}>{r.name}</option>)}</select></label>}
   <Button disabled={busy||!target||reason.trim().length<3} onClick={()=>perform(()=>api.put(`/incidents/${incidentId}/assignments`,{user_id:target,role:role||null,section_id:role==='FueAss'&&support==='EL'?null:section||null,supports:role==='FueAss'?support:null,resource_id:role==='Helfer'?resource:null,reason}))}>Begründet übernehmen</Button>{role==='FueAss'&&<Button variant="outline" disabled={busy||!target||reason.trim().length<3} onClick={()=>perform(()=>api.put(`/incidents/${incidentId}/assistants/${target}/support`,{supports:support,section_id:support==='AL'?section:null,reason}))}>Bestehende FüAss organisatorisch zuordnen (EL)</Button>}
  </section>}
  {mayManageArchive&&selected?.status==='abgeschlossen'&&<section className="els-surface p-5 space-y-3"><h2 className="text-heading">Individuelle Archivlesefreigabe</h2><p>Diese Verwaltung verleiht der verwaltenden Person keine Einsicht in Einsatz- oder Patientendaten.</p>
   <label className="block">Person<select className="block bg-background border p-2" value={grantTarget} onChange={e=>setGrantTarget(e.target.value)}><option value="">Person wählen</option>{accounts.map(u=><option key={u.id} value={u.id}>{u.display_name}</option>)}</select></label>
   <label className="block">Gültigkeit in Tagen<Input type="number" min={1} max={3650} value={days} onChange={e=>setDays(Number(e.target.value))}/></label>
   {[false,true].map(revoke=><Button key={String(revoke)} variant={revoke?'outline':'default'} disabled={busy||!grantTarget||reason.trim().length<3} onClick={()=>perform(()=>api.put(`/incidents/${incidentId}/archive-grants`,{user_id:grantTarget,days,revoke,reason}))}>{revoke?'Freigabe widerrufen':'Lesefreigabe erteilen'}</Button>)}
  </section>}
  <ArchiveCorrectionPanel incident={selected} reason={reason}/>
 </main>;
}
