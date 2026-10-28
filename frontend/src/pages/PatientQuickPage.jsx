import * as React from 'react';
import { useNavigate } from 'react-router-dom';
import { useIncidents } from '@/context/IncidentContext';
import { usePatients } from '@/context/PatientContext';
import { listAbschnitte } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

const CATEGORIES = [
  { level: 'S1', label: 'S1', color: 'bg-red-600 hover:bg-red-700 text-white', key: '1' },
  { level: 'S2', label: 'S2', color: 'bg-amber-500 hover:bg-amber-600 text-black', key: '2' },
  { level: 'S3', label: 'S3', color: 'bg-green-600 hover:bg-green-700 text-white', key: '3' },
  { level: 'S0', label: 'S0', color: 'bg-slate-600 hover:bg-slate-700 text-white', key: '0' },
  { level: null, label: 'Dummy', color: 'bg-slate-500 hover:bg-slate-600 text-white', key: 'd' },
];

export default function PatientQuickPage() {
  const { activeIncident } = useIncidents();
  const { create, createDummy } = usePatients();
  const navigate = useNavigate();
  const [sections, setSections] = React.useState([]);
  const [activeSection, setActiveSection] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  React.useEffect(() => {
    if (!activeIncident?.id) return;
    let cancelled = false;
    listAbschnitte(activeIncident.id, { aktiv: true })
      .then(list => {
        if (cancelled) return;
        const enabled = list.filter(x => x.aktiv);
        setSections(enabled);
        setActiveSection(old => enabled.some(s=>s.id === old) ? old : null);
      })
      .catch(() => toast.error('Einsatzabschnitte konnten nicht geladen werden'));
    return () => { cancelled = true; };
  }, [activeIncident?.id]);
  const add = React.useCallback(async (sectionId, level) => {
    if (busy || !activeIncident || activeIncident.status !== 'operativ') return;
    setBusy(true);
    try {
      const payload = { abschnitt_id: sectionId, status: 'wartend' };
      let newPatient;
      if (level) newPatient = await create({ ...payload, sichtung: level });
      else newPatient = await createDummy(payload);
      toast.success(`Pat. ${newPatient?.kennung || ''} angelegt – Ressource noch nicht zugewiesen`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Patient konnte nicht angelegt werden');
    } finally { setBusy(false); }
  }, [busy, activeIncident, create, createDummy]);
  React.useEffect(() => {
    const handler = event => {
      if (event.repeat || event.metaKey || event.ctrlKey || event.altKey ||
          ['input','textarea','select'].includes(event.target?.tagName?.toLowerCase()) ||
          event.target?.isContentEditable) return;
      const category = CATEGORIES.find(c => c.key === event.key.toLowerCase());
      if (!category) return;
      event.preventDefault();
      add(activeSection, category.level);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [activeSection, add]);
  if (!activeIncident) return <p className="p-6">Bitte zunächst einen Incident wählen.</p>;
  const allSections = [...sections, { id: null, name: 'Abschnitt unbekannt', beschreibung: 'Meldung ohne eindeutigen Auffindeabschnitt' }];
  return <main className="mx-auto max-w-[1400px] p-6 space-y-4">
    <div className="flex items-center justify-between gap-3">
      <div><h1 className="text-2xl font-semibold">Patienten-Schnellerfassung</h1>
        <p className="text-sm text-muted-foreground">Pro Abschnitt direkt S1/S2/S3/S0 oder Dummy erfassen. Keine automatische Ressourcenzuweisung.</p></div>
      <Button variant="outline" onClick={()=>navigate('/patienten')}>Zur Patientenliste</Button>
    </div>
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {allSections.map(section => <section key={section.id || 'unknown'}
        className={`els-surface p-4 space-y-3 border-2 ${activeSection === section.id ? 'border-primary' : 'border-transparent'}`}>
        <button type="button" className="text-left w-full" onClick={()=>setActiveSection(section.id)}
          aria-pressed={activeSection === section.id} title="Abschnitt für Tastaturerfassung auswählen">
          <h2 className="font-semibold">{section.name}</h2>
          <p className="text-xs text-muted-foreground">{section.beschreibung || 'Abschnitt für Tastatur erfassbar'}</p>
          {activeSection === section.id && <span className="text-xs text-primary">Tastaturziel ausgewählt</span>}
        </button>
        <div className="grid grid-cols-5 gap-1">
          {CATEGORIES.map(c => <button key={c.label} type="button" disabled={busy || activeIncident.status !== 'operativ'}
            className={`rounded-md py-3 font-semibold text-sm disabled:opacity-50 ${c.color}`}
            onClick={()=>{setActiveSection(section.id);add(section.id,c.level);}}>
            {c.label}
          </button>)}
        </div>
      </section>)}
    </div>
    <p className="text-xs text-muted-foreground">Tastatur im ausgewählten Abschnitt: 1 = S1, 2 = S2, 3 = S3, 0 = S0, D = Dummy. Ohne ausgewählten Abschnitt: unbekannt.</p>
  </main>;
}
