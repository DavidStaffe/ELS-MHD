import * as React from 'react';
import { api } from '@/lib/api';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

export function LifecycleDialog({ pending, onDone }) {
 const [reason,setReason]=React.useState('');
 const [preview,setPreview]=React.useState(null);
 const [confirm,setConfirm]=React.useState(false);
 const [leaders,setLeaders]=React.useState([]);
 const [leader,setLeader]=React.useState('');
 const [error,setError]=React.useState('');
 const [busy,setBusy]=React.useState(false);
 React.useEffect(()=>{
   setReason('');setPreview(null);setConfirm(false);setError('');setLeader('');setLeaders([]);
   if(!pending)return;
   if(pending.action==='close')api.get(`/incidents/${pending.id}/closure-preview`).then(r=>setPreview(r.data)).catch(()=>setError('Abschlussprüfung fehlgeschlagen.'));
   else api.get('/leadership-candidates').then(r=>setLeaders(r.data)).catch(()=>{});
 },[pending]);
 if(!pending)return null;
 const hasOpen=preview&&Object.values(preview).some(v=>Array.isArray(v)&&v.length);
 const submit=async()=>{setBusy(true);setError('');try{
   await api.post(`/incidents/${pending.id}/${pending.action}`,{reason,...(pending.action==='close'?{confirm_open:confirm}:{el_user_id:leader||null})});
   onDone(true);
 }catch(e){setError(typeof e?.response?.data?.detail==='string'?e.response.data.detail:'Offene Vorgänge oder Berechtigungen haben sich geändert. Bitte erneut prüfen.');if(pending.action==='close'){api.get(`/incidents/${pending.id}/closure-preview`).then(r=>setPreview(r.data)).catch(()=>{});setConfirm(false);}}finally{setBusy(false);}};
 return <Dialog open onOpenChange={open=>{if(!open&&!busy)onDone(false);}}><DialogContent>
  <DialogHeader><DialogTitle>{pending.action==='close'?'Einsatz abschließen':'Einsatz wieder eröffnen'}</DialogTitle><DialogDescription>Patienten-, Ressourcen-, Transport- und Dispositionszustände bleiben unverändert.</DialogDescription></DialogHeader>
  {hasOpen&&<section className="space-y-2"><p>Es bestehen offene Vorgänge:</p>{Object.entries(preview).map(([key,items])=><p key={key}>{({patients:'Patienten',transports:'Transporte',resources:'Gebundene Ressourcen',dispositions:'Offene Dispositionen'})[key]||key}: {items.length}</p>)}<label className="block"><input type="checkbox" checked={confirm} onChange={e=>setConfirm(e.target.checked)}/> Ich bestätige den Abschluss trotz aller offenen Vorgänge ausdrücklich.</label></section>}
  {pending.action==='reopen'&&!!leaders.length&&<label className="block">Ersatz-EL, falls bisherige EL nicht mehr geeignet/aktiv<select className="block border bg-background p-2" value={leader} onChange={e=>setLeader(e.target.value)}><option value="">Bisherige EL nach Prüfung</option>{leaders.map(u=><option key={u.id} value={u.id}>{u.display_name}</option>)}</select></label>}
  <label className="block">Verpflichtende Begründung<Input value={reason} onChange={e=>setReason(e.target.value)} minLength={3}/></label>
  {error&&<p role="alert">{error}</p>}
  <Button disabled={busy||reason.trim().length<3||(pending.action==='close'&&(!preview||(hasOpen&&!confirm)))} onClick={submit}>Begründet bestätigen</Button><Button variant="outline" disabled={busy} onClick={()=>onDone(false)}>Abbrechen</Button>
 </DialogContent></Dialog>;
}
