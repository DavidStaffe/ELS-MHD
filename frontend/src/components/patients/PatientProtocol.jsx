import * as React from 'react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';

const SECTIONS = [
  ['stammdaten', 'Stammdaten'],
  ['anamnese', 'SAMPLER(S)'],
  ['erstbefund', 'xABCDE / BEFAST'],
  ['verlauf', 'Verlauf'],
  ['massnahmen', 'Maßnahmen'],
  ['uebergabe', 'Übergabe'],
];
const ANAMNESE = [
  ['beschwerden', 'Leitsymptom / Notfallgeschehen'],
  ['symptome', 'S – Symptome'],
  ['allergien', 'A – Allergien / Unverträglichkeiten'],
  ['medikation', 'M – Medikamente'],
  ['vorgeschichte', 'P – Vorerkrankungen / Operationen'],
  ['letzte_mahlzeit', 'L – Letzte Mahlzeit'],
  ['ereignis', 'E – Ereignis / Auslöser'],
  ['risikofaktoren', 'R – Risikofaktoren'],
  ['schwangerschaft', 'S – Schwangerschaft (falls relevant)'],
];
const ABCDE = [
  ['x_blutung', 'x – Kritische Blutung'],
  ['a_atemweg', 'A – Atemweg'],
  ['b_atmung', 'B – Atmung'],
  ['c_kreislauf', 'C – Kreislauf'],
  ['d_neurologie', 'D – Neurologie'],
  ['e_exposition', 'E – Exposition / Umgebung'],
];
const BEFAST = [
  ['befast_balance', 'Balance – Gleichgewicht'],
  ['befast_eyes', 'Eyes – Sehstörung'],
  ['befast_face', 'Face – Gesicht'],
  ['befast_arm', 'Arm – Kraft / Sensibilität'],
  ['befast_speech', 'Speech – Sprache'],
];
const VITALS = [
  ['rr_sys', 'RR sys.', 'mmHg'],
  ['rr_dia', 'RR dia.', 'mmHg'],
  ['puls', 'Puls', '/min'],
  ['atemfrequenz', 'AF', '/min'],
  ['spo2', 'SpO₂', '%'],
  ['temperatur', 'Temp.', '°C'],
  ['gcs', 'GCS', '3–15'],
  ['blutzucker_mgdl', 'BZ', 'mg/dl'],
  ['schmerz_nrs', 'Schmerz', '0–10'],
];
const TYPES = [
  ['allgemein', 'Allgemein'], ['atemweg', 'Atemweg'], ['beatmung', 'Beatmung'],
  ['kreislauf', 'Kreislauf'], ['medikament', 'Medikament'],
  ['immobilisation', 'Immobilisation'], ['sonstiges', 'Sonstiges'],
];
const cx = 'w-full min-h-10 rounded-md border border-border bg-background px-3 py-2 text-sm';
const caption = 'mb-1 block text-xs font-medium text-muted-foreground';
const nowTime = () => new Date().toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
const today = () => { const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 10); };
const valueOf = (v) => v ?? '';

function TextField({ label, value, onChange, type = 'text', rows, placeholder, ...rest }) {
  return (
    <label className="block min-w-0">
      <span className={caption}>{label}</span>
      {rows ? (
        <textarea className={cx} rows={rows} value={valueOf(value)}
          onChange={(e) => onChange(e.target.value)} placeholder={placeholder} {...rest} />
      ) : (
        <input className={cx} type={type} value={valueOf(value)}
          onChange={(e) => onChange(e.target.value)} placeholder={placeholder} {...rest} />
      )}
    </label>
  );
}
function Pick({ label, value, onChange, options }) {
  return (
    <label className="block min-w-0">
      <span className={caption}>{label}</span>
      <select className={cx} value={valueOf(value)} onChange={(e) => onChange(e.target.value)}>
        {options.map(([v, title]) => <option key={v} value={v}>{title}</option>)}
      </select>
    </label>
  );
}
const BEFAST_CHOICES = [
  ['nicht_erhoben', 'Nicht erhoben'], ['unauffaellig', 'Unauffällig'], ['auffaellig', 'Auffällig'],
];
const setRow = (rows, index, key, value) => rows.map((row, i) => i === index ? { ...row, [key]: value } : row);

export function PatientProtocol({ patient, onUpdate }) {
  const [section, setSection] = React.useState('stammdaten');
  const [draft, setDraft] = React.useState({});
  const [dirty, setDirty] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState('');
  const [success, setSuccess] = React.useState('');
  const [reason, setReason] = React.useState('');
  const protocol = patient.protokoll || {};
  const version = protocol.version || 0;
  const [loadedVersion, setLoadedVersion] = React.useState(version);
  const currentTab = React.useRef({ id: patient.id, section });
  const completed = ['uebergeben', 'entlassen'].includes(patient.status);

  React.useEffect(() => {
    const changedTab = currentTab.current.id !== patient.id || currentTab.current.section !== section;
    currentTab.current = { id: patient.id, section };
    // Do not discard unsaved clinical notes when SSE reports an external update.
    if (changedTab || !dirty) {
      setDraft(protocol[section] || {});
      setLoadedVersion(version);
      setDirty(false);
      setReason('');
      setError('');
    }
  // Unsaved changes keep their original loadedVersion until explicitly reloaded.
  }, [patient.id, version, section]); // eslint-disable-line react-hooks/exhaustive-deps

  const edit = (key, value) => {
    setDraft((old) => ({ ...old, [key]: value }));
    setDirty(true);
    setSuccess('');
    setError('');
  };
  const switchSection = (next) => {
    if (next === section) return;
    if (dirty && !window.confirm('Ungespeicherte Protokolleingaben verwerfen?')) return;
    setSection(next);
    setSuccess('');
  };
  const save = async () => {
    setSaving(true); setError(''); setSuccess('');
    try {
      const { data } = await api.patch('/patients/' + patient.id + '/protocol', {
        section,
        data: draft,
        expected_version: loadedVersion,
        reason,
      });
      onUpdate?.(data);
      setDirty(false);
      setSuccess('Gespeichert · Revision ' + data.protokoll.version);
    } catch (e) {
      const detail = e?.response?.data?.detail;
      if (e?.response?.status === 409) {
        setError('Zwischenzeitliche Änderung oder gesperrter Incident: Bitte Seite aktualisieren, Änderungen prüfen und erneut speichern.');
      } else {
        setError(typeof detail === 'string' ? detail : 'Eingaben konnten nicht gespeichert werden. Bitte prüfen.');
      }
    } finally { setSaving(false); }
  };
  const reload = async () => {
    if (dirty && !window.confirm('Ungespeicherte Protokolleingaben wirklich verwerfen?')) return;
    try {
      const { data } = await api.get('/patients/' + patient.id);
      onUpdate?.(data);
      setDraft(data.protokoll?.[section] || {});
      setLoadedVersion(data.protokoll?.version || 0);
      setDirty(false);
      setError('');
    } catch {
      setError('Aktueller Protokollstand konnte nicht geladen werden.');
    }
  };
  const entries = draft.eintraege || [];
  const rows = draft.werte || [];

  return (
    <section className="rounded-xl border border-border bg-card p-4 sm:p-5" data-testid="patient-protocol">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold">Medizinisches Einsatzprotokoll</h2>
          <p className="text-xs text-muted-foreground">
            DIVI-orientiert · Patient {patient.kennung} · Revision {version}
            {protocol.updated_at ? ' · Zuletzt bearbeitet: ' + new Date(protocol.updated_at).toLocaleString('de-DE') : ''}
          </p>
        </div>
        <span className="rounded-md border border-border px-2 py-1 text-xs">Ohne Klardaten</span>
      </div>
      <p className="mb-4 text-xs text-muted-foreground">
        Keine Patientennamen, Anschriften, Versicherungsnummern oder andere identifizierende Angaben eintragen – auch nicht in Freitextfelder.
        Die Scores dienen nur als Erhebungshilfen; eine automatisierte medizinische Beurteilung findet nicht statt.
      </p>

      <nav aria-label="Protokollabschnitte" className="mb-4 flex flex-wrap gap-1.5">
        {SECTIONS.map(([key, name]) => (
          <button key={key} type="button" onClick={() => switchSection(key)}
            className={'rounded-md border px-3 py-2 text-sm ' +
              (section === key ? 'border-primary bg-primary/10 font-semibold' : 'border-border hover:bg-accent')}
            aria-current={section === key ? 'page' : undefined}>{name}</button>
        ))}
      </nav>

      {section === 'stammdaten' && (
        <div className="grid gap-3 sm:grid-cols-2">
          <TextField label="Geburtsdatum" type="date" max={new Date().toISOString().slice(0, 10)}
            value={draft.geburtsdatum} onChange={(v) => edit('geburtsdatum', v || null)} />
          <Pick label="Geschlecht" value={draft.geschlecht || ''} onChange={(v) => edit('geschlecht', v || null)}
            options={ [['', 'Nicht angegeben'], ['weiblich', 'Weiblich'], ['maennlich', 'Männlich'], ['divers', 'Divers'], ['unbekannt', 'Unbekannt']] } />
        </div>
      )}

      {section === 'anamnese' && (
        <div className="grid gap-3 sm:grid-cols-2">
          {ANAMNESE.map(([key, label]) => (
            <TextField key={key} label={label} value={draft[key]} rows={key === 'beschwerden' ? 3 : 2}
              onChange={(v) => edit(key, v)} />
          ))}
        </div>
      )}

      {section === 'erstbefund' && (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            {ABCDE.map(([key, label]) => (
              <TextField key={key} label={label} rows={2} value={draft[key]} onChange={(v) => edit(key, v)} />
            ))}
          </div>
          <div className="border-t border-border pt-3">
            <h3 className="mb-2 text-sm font-semibold">(BE)FAST-Screening</h3>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {BEFAST.map(([key, label]) => (
                <Pick key={key} label={label} value={draft[key] || 'nicht_erhoben'}
                  onChange={(v) => edit(key, v)} options={BEFAST_CHOICES} />
              ))}
              <TextField label="Time – Symptombeginn / last seen well" value={draft.befast_time}
                onChange={(v) => edit('befast_time', v)} placeholder="z. B. 14:20" />
            </div>
          </div>
        </div>
      )}

      {section === 'verlauf' && (
        <div className="space-y-3">
          <p className="text-xs text-muted-foreground">Messzeit und Vitalwerte protokollieren. SpO₂-Skala 2 nur bei entsprechender klinischer Indikation verwenden. NEWS2 wird nicht automatisch errechnet.</p>
          {rows.map((row, i) => (
            <div key={i} className="rounded-md border border-border p-3">
              <div className="mb-2 flex items-center justify-between">
                <strong className="text-sm">Messung {i + 1}</strong>
                <button type="button" className="text-xs text-destructive" onClick={() => edit('werte', rows.filter((_, j) => j !== i))}>Entfernen</button>
              </div>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-6">
                <TextField label="Datum" type="date" value={row.datum}
                  onChange={(v) => edit('werte', setRow(rows, i, 'datum', v || null))} />
                <TextField label="Uhrzeit" type="time" value={row.zeit}
                  onChange={(v) => edit('werte', setRow(rows, i, 'zeit', v))} />
                {VITALS.map(([field, label, unit]) => (
                  <TextField key={field} label={label + ' (' + unit + ')'} type="number" step={field === 'temperatur' ? '0.1' : '1'}
                    value={row[field]} onChange={(v) => edit('werte', setRow(rows, i, field, v === '' ? null : Number(v)))} />
                ))}
                <Pick label="Sauerstoffgabe" value={row.o2_gabe == null ? '' : String(row.o2_gabe)}
                  onChange={(v) => edit('werte', setRow(rows, i, 'o2_gabe', v === '' ? null : v === 'true'))}
                  options={ [['', 'Unbekannt'], ['false', 'Raumluft'], ['true', 'O₂-Gabe']] } />
                <Pick label="SpO₂-Skala" value={row.spo2_skala == null ? '' : String(row.spo2_skala)}
                  onChange={(v) => edit('werte', setRow(rows, i, 'spo2_skala', v ? Number(v) : null))}
                  options={ [['', 'Nicht festgelegt'], ['1', 'Skala 1'], ['2', 'Skala 2']] } />
              </div>
            </div>
          ))}
          <Button variant="outline" size="sm" type="button" disabled={rows.length >= 48}
            onClick={() => edit('werte', [...rows, { datum: today(), zeit: nowTime() }])}>+ Messung hinzufügen</Button>
          <TextField label="Verlaufsbemerkung" rows={3} value={draft.notiz} onChange={(v) => edit('notiz', v)} />
        </div>
      )}

      {section === 'massnahmen' && (
        <div className="space-y-3">
          {entries.map((entry, i) => (
            <div key={i} className="rounded-md border border-border p-3">
              <div className="mb-2 flex items-center justify-between">
                <strong className="text-sm">Maßnahme {i + 1}</strong>
                <button type="button" className="text-xs text-destructive" onClick={() => edit('eintraege', entries.filter((_, j) => j !== i))}>Entfernen</button>
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <TextField label="Datum" type="date" value={entry.datum}
                  onChange={(v) => edit('eintraege', setRow(entries, i, 'datum', v || null))} />
                <TextField label="Uhrzeit" type="time" value={entry.zeit}
                  onChange={(v) => edit('eintraege', setRow(entries, i, 'zeit', v))} />
                <Pick label="Art" value={entry.typ || 'allgemein'} options={TYPES}
                  onChange={(v) => edit('eintraege', setRow(entries, i, 'typ', v))} />
                <TextField label="Maßnahme / Medikament" value={entry.beschreibung}
                  onChange={(v) => edit('eintraege', setRow(entries, i, 'beschreibung', v))} />
                <TextField label="Dosis / Menge (mit Einheit)" value={entry.dosis}
                  onChange={(v) => edit('eintraege', setRow(entries, i, 'dosis', v))} />
                <TextField label="Applikationsweg" value={entry.appl_weg}
                  onChange={(v) => edit('eintraege', setRow(entries, i, 'appl_weg', v))} />
                <TextField label="Wirkung / Verlauf" value={entry.wirkung}
                  onChange={(v) => edit('eintraege', setRow(entries, i, 'wirkung', v))} />
              </div>
            </div>
          ))}
          <Button type="button" size="sm" variant="outline" disabled={entries.length >= 48}
            onClick={() => edit('eintraege', [...entries, { datum: today(), zeit: nowTime(), typ: 'allgemein', beschreibung: '' }])}>+ Maßnahme hinzufügen</Button>
        </div>
      )}

      {section === 'uebergabe' && (
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Pick label="Disposition / Verbleib laut Protokoll" value={draft.art || 'offen'}
              onChange={(v) => edit('art', v)}
              options={ [['offen', 'Offen'], ['transport', 'Transport'], ['uebergeben', 'Übergeben'], ['entlassen', 'Entlassen'], ['transportverweigerung', 'Transportverweigerung']] } />
            <TextField label="Datum" type="date" value={draft.datum} onChange={(v) => edit('datum', v || null)} />
            <TextField label="Uhrzeit" type="time" value={draft.zeit} onChange={(v) => edit('zeit', v)} />
            <TextField label="Ziel / Einrichtung (keine Personennamen)" value={draft.ziel} onChange={(v) => edit('ziel', v)} />
            <TextField label="Empfangende Funktion / Team (keine Personennamen)" value={draft.empfangende_funktion}
              onChange={(v) => edit('empfangende_funktion', v)} />
          </div>
          <TextField label="SINNHAFT – Übergabeinhalt / Anmerkungen" rows={4} value={draft.sinnhaft}
            onChange={(v) => edit('sinnhaft', v)}
            placeholder="Situation, Identifikation über Kennung, Notfallgeschehen, Priorität, Handlungen, Anamnese, Fazit, Teamfragen" />
          {draft.art === 'transportverweigerung' && (
            <div className="rounded-md border border-border p-3 space-y-2">
              <p className="text-sm font-medium">Transportverweigerung (ohne digitale Unterschrift)</p>
              <label className="flex gap-2 text-sm">
                <input type="checkbox" checked={!!draft.aufklaerung_dokumentiert}
                  onChange={(e) => edit('aufklaerung_dokumentiert', e.target.checked)} />
                Aufklärung über Risiken und Transportempfehlung dokumentiert
              </label>
              <label className="flex gap-2 text-sm">
                <input type="checkbox" checked={!!draft.verweigerung_bezeugt}
                  onChange={(e) => edit('verweigerung_bezeugt', e.target.checked)} />
                Verweigerung bezeugt (ohne Zeugenklardaten)
              </label>
              <p className="text-xs text-muted-foreground">Diese Eingabe ersetzt keine rechtswirksame unterschriebene Erklärung.</p>
            </div>
          )}
          <p className="text-xs text-muted-foreground">
            Hinweis: Die tatsächliche Transportdisposition und der Patientenstatus werden weiterhin in ELS-MHD separat geführt.
          </p>
        </div>
      )}

      {completed && (
        <div className="mt-4">
          <TextField label="Begründung für nachträgliche Ergänzung/Korrektur (mind. 10 Zeichen)" rows={2}
            value={reason} onChange={setReason} />
        </div>
      )}
      {dirty && version !== loadedVersion && (
        <p role="alert" className="mt-4 text-sm text-destructive">
          Eine neue Protokollversion liegt vor. Dein Entwurf wurde beibehalten; bitte die Änderungen abgleichen.
        </p>
      )}
      {error && <p role="alert" className="mt-4 text-sm text-destructive">{error}</p>}
      {success && <p role="status" className="mt-4 text-sm text-status-green">{success}</p>}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-border pt-4">
        <span className="text-xs text-muted-foreground">
          {dirty ? 'Nicht gespeicherte Eingaben' : 'Alle angezeigten Eingaben gespeichert'}
        </span>
        <div className="flex gap-2">
          <Button variant="outline" type="button" onClick={reload} disabled={saving}>Neu laden</Button>
        <Button onClick={save} type="button" disabled={!dirty || saving || (completed && reason.trim().length < 10)}
          data-testid="protocol-save">{saving ? 'Speichert …' : 'Abschnitt speichern'}</Button>
        </div>
      </div>
    </section>
  );
}
