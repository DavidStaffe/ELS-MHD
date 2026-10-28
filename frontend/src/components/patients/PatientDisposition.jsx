import * as React from 'react';
import { api } from '@/lib/api';
import { useRole } from '@/context/RoleContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';

const SIGHTINGS = ['S1', 'S2', 'S3', 'S0'];

export function PatientDisposition({ patient, resources, onRefresh }) {
  const { role } = useRole();
  const [suggestions, setSuggestions] = React.useState([]);
  const [loading, setLoading] = React.useState(false);
  const [selectedReporter, setSelectedReporter] = React.useState('none');
  const [sighting, setSighting] = React.useState(patient.sichtung || 'S2');
  const [note, setNote] = React.useState('');
  const isOperator = role === 'einsatzleiter' || role === 'fuehrungsassistenz';
  React.useEffect(() => { setSighting(patient.sichtung || 'S2'); }, [patient.id, patient.sichtung]);
  const refreshSuggestions = React.useCallback(async () => {
    if (patient.zugewiesene_ressource_id) return;
    setLoading(true);
    try {
      const { data } = await api.get(`/patients/${patient.id}/resource-suggestions`);
      setSuggestions(data);
    } catch { setSuggestions([]); } finally { setLoading(false); }
  }, [patient.id, patient.zugewiesene_ressource_id]);
  React.useEffect(() => { refreshSuggestions(); }, [refreshSuggestions]);
  const action = async (fn, success) => {
    setLoading(true);
    try { await fn(); toast.success(success); await onRefresh(); await refreshSuggestions(); }
    catch (e) { toast.error(e?.response?.data?.detail || 'Aktion fehlgeschlagen'); }
    finally { setLoading(false); }
  };
  const bound = resources.find(r => r.id === patient.zugewiesene_ressource_id);
  return <div className="space-y-4">
    <section className="els-surface p-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold">Sichtung per Funk bestätigen</h2>
        <span className="text-sm text-muted-foreground">
          {patient.sichtung ? `${patient.sichtung} · ${patient.sichtung_bestaetigt ? 'bestätigt' : 'vorläufig'}` : 'Noch ohne Sichtung'}
        </span>
      </div>
      <p className="text-xs text-muted-foreground">Die tatsächliche Sichtung wird durch die meldende Ressource per Funk übermittelt. Auch unveränderte Bestätigungen werden protokolliert.</p>
      <div className="flex flex-wrap gap-2">{SIGHTINGS.map(level =>
        <Button key={level} type="button" variant={sighting === level ? 'default' : 'outline'}
          onClick={()=>setSighting(level)} disabled={!isOperator || loading}>{level}</Button>)}</div>
      <select aria-label="Meldende Ressource" className="rounded border border-input bg-background p-2 w-full"
        value={selectedReporter} onChange={e=>setSelectedReporter(e.target.value)} disabled={!isOperator}>
        <option value="none">Meldende Ressource nicht bekannt</option>
        {resources.map(r=><option key={r.id} value={r.id}>{r.name}</option>)}
      </select>
      <Input value={note} onChange={e=>setNote(e.target.value)} placeholder="Bemerkung zur Sichtung (optional)" disabled={!isOperator}/>
      <Button disabled={!isOperator || loading} onClick={()=>action(
        ()=>api.post(`/patients/${patient.id}/sichtung-confirm`,
          { sichtung: sighting, meldende_ressource_id: selectedReporter === 'none' ? null : selectedReporter, bemerkung: note }),
        'Sichtung per Funk bestätigt und protokolliert')}>Sichtung bestätigen / ändern</Button>
      <p className="text-xs text-muted-foreground">Erfasst-durch-Klarname wird nach Einführung des verbindlichen Logins ergänzt.</p>
    </section>
    <section className="els-surface p-4 space-y-3">
      <h2 className="font-semibold">Ressourcendisposition</h2>
      {bound ? <>
        <p>Gebunden: <strong>{bound.name}</strong></p>
        <p className="text-xs text-muted-foreground">Auch nach Übergabe oder Fallabschluss bleibt die Ressource gebunden, bis sie ausdrücklich freigemeldet wird.</p>
        {role === 'einsatzleiter' && <>
          <Button variant="outline" disabled={loading} onClick={()=>action(
            ()=>api.post(`/resources/${bound.id}/release-from-patient`, {}),
            'Ressource intern freigemeldet')}>Ressource freimelden (EL)</Button>
        </>}
      </> : <>
        <p className="text-xs text-muted-foreground">Vorschläge sind nicht automatisch verbindlich. Ortsabstände sind Luftlinie und GPS-Daten können veraltet sein.</p>
        <Button variant="outline" size="sm" onClick={refreshSuggestions} disabled={loading}>Vorschläge aktualisieren</Button>
        {suggestions.length === 0 && <p className="text-sm">Keine freien Ressourcen gefunden.</p>}
        <div className="space-y-2">{suggestions.map(s=><div key={s.resource_id}
          className="flex items-center justify-between gap-2 border rounded-md p-2">
          <div><div className="font-medium">{s.name}</div>
            <div className="text-xs text-muted-foreground">
              {s.reason === 'eigener_abschnitt' ? 'Eigener Abschnitt' :
                s.reason === 'positionsnaehe' ? 'Positionsnähe (GPS ≤ 5 Min. alt)' :
                s.reason === 'nachbarabschnitt' ? 'Benachbarter Abschnitt (Kartengrenzen)' :
                  'Sonstige freie Ressource'}
              {s.distance_km_airline !== null ? ` · ${s.distance_km_airline} km Luftlinie` : ''}
              {s.abschnitt_name ? ` · ${s.abschnitt_name}` : ''}
            </div></div>
          <Button size="sm" disabled={!isOperator || loading} onClick={()=>action(
            ()=>api.post(`/patients/${patient.id}/assign-resource`, { resource_id: s.resource_id }),
            'Ressource zugewiesen')}>Zuweisen</Button>
        </div>)}</div>
      </>}
    </section>
  </div>;
}
