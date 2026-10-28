import * as React from 'react';
import { api } from '@/lib/api';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { useRole } from '@/context/RoleContext';

const fields = {messages:{text:'Inhalt',absender:'Absender',empfaenger:'Empfänger'},patients:{notiz:'Medizinische Notiz',sichtung:'Sichtung',auffindeort:'Auffindeort'},incidents:{name:'Titel',ort:'Ort',beschreibung:'Beschreibung'}};
export function ArchiveCorrectionPanel({ incident, reason }) {
 const { user } = useRole();
 const [kind,setKind] = React.useState('messages');
 const [records,setRecords] = React.useState([]);
 const [recordId,setRecordId] = React.useState('');
 const [field,setField] = React.useState('text');
 const [value,setValue] = React.useState('');
 const [message,setMessage] = React.useState('');
 const [busy,setBusy] = React.useState(false);
 const record=records.find(r=>r.id===recordId);
 const load=React.useCallback(async()=>{
   if(!incident?.id)return;
   setMessage('');setRecords([]);setRecordId('');
   try {const {data}=await api.get(kind==='incidents'?`/incidents/${incident.id}`:`/incidents/${incident.id}/${kind}`);setRecords(kind==='incidents'?[data]:data);}
   catch {setMessage('Notwendige Archiv- oder medizinische Leseberechtigung fehlt.');}
 },[incident?.id,kind]);
 React.useEffect(()=>{load();},[load]);
 React.useEffect(()=>{setValue(record?.[field]??'');},[record,field]);
 if(!incident||incident.status!=='abgeschlossen'||incident.restricted)return null;
 const allowed=user.permissions.includes(kind==='patients'?'archives.patients.correct':'archives.correct');
 if(!user.permissions.some(p=>['archives.correct','archives.patients.correct'].includes(p)))return null;
 const submit=async()=>{setBusy(true);setMessage('');try{await api.post(`/incidents/${incident.id}/corrections/${kind}/${recordId}`,{reason,changes:{[field]:value}});await load();setMessage('Korrektur mit vollständiger Versionshistorie gespeichert. Archiv bleibt geschlossen.');}catch(e){setMessage(typeof e?.response?.data?.detail==='string'?e.response.data.detail:'Korrektur abgelehnt. Rechte, Feldwert und Begründung prüfen.');}finally{setBusy(false);}};
 return <section className="els-surface p-5 space-y-3"><h2 className="text-heading">Dokumentation im Archiv korrigieren</h2><p>Eine berechtigte Person genügt. Jede Änderung benötigt einen Grund und erhält die vorherige Fassung.</p>
  <label className="block">Dokumentationsart<select className="block border bg-background p-2" value={kind} onChange={e=>{setKind(e.target.value);setField(Object.keys(fields[e.target.value])[0]);}}><option value="messages">Einsatztagebuch</option><option value="patients">Medizinische Patientendokumentation</option><option value="incidents">Allgemeine Einsatzdokumentation</option></select></label>
  <label className="block">Eintrag<select className="block border bg-background p-2 w-full" value={recordId} onChange={e=>setRecordId(e.target.value)}><option value="">Eintrag wählen</option>{records.map(r=><option key={r.id} value={r.id}>{r.kennung||r.name||r.text?.slice(0,80)||'Dokumentation'}</option>)}</select></label>
  <label className="block">Feld<select className="block border bg-background p-2" value={field} onChange={e=>setField(e.target.value)}>{Object.entries(fields[kind]).map(([k,label])=><option key={k} value={k}>{label}</option>)}</select></label>
  <label className="block">Korrigierter Wert<Input value={value} onChange={e=>setValue(e.target.value)}/></label>
  <Button disabled={busy||!allowed||!recordId||reason.trim().length<3} onClick={submit}>Begründete Archivkorrektur speichern</Button>
  {message&&<p role="status">{message}</p>}
  {record?.versions?.length>0&&<details><summary>Versionshistorie ({record.versions.length})</summary>{record.versions.map((v,i)=><section className="border rounded p-3 my-2" key={i}><p>{v.at} · {v.display_name||v.username} · {v.role||'Archivberechtigung'}</p><p>Grund: {v.reason}</p>{Object.entries(fields[kind]).map(([k,label])=><div key={k}><p>{label} vorher: {v.before[k]??'–'}</p><p>{label} nachher: {v.after[k]??'–'}</p></div>)}</section>)}</details>}
 </section>;
}
