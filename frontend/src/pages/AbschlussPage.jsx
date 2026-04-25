import * as React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import {
  StatusBadge,
  SectionCard,
  ConfirmModal,
} from '@/components/primitives';
import { useIncidents } from '@/context/IncidentContext';
import { useRole } from '@/context/RoleContext';
import {
  getAbschlussCheck,
  getReport,
  listReportVersions,
  createReportVersion,
  patchIncidentMeta,
} from '@/lib/api';
import {
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Printer,
  FileCheck2,
  History,
  Save,
  ArrowLeft,
  FileText,
  Lock,
  RefreshCw,
} from 'lucide-react';
import { toast } from 'sonner';

const STATUS_LABEL = {
  wartend: 'Wartend',
  in_behandlung: 'In Behandlung',
  transportbereit: 'Transportbereit',
  uebergeben: 'Uebergeben',
  entlassen: 'Entlassen',
};

const TRANSPORT_STATUS_LABEL = {
  offen: 'Offen',
  zugewiesen: 'Zugewiesen',
  unterwegs: 'Unterwegs',
  abgeschlossen: 'Abgeschlossen',
};

function fmtDT(iso) {
  if (!iso) return '–';
  try {
    const d = new Date(iso);
    return d.toLocaleString('de-DE', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function fmtMin(n) {
  if (n === null || n === undefined) return '–';
  return `${Math.round(n)} min`;
}

function NoIncidentState() {
  const navigate = useNavigate();
  return (
    <div className="mx-auto w-full max-w-xl px-6 py-16">
      <div
        className="els-surface flex flex-col items-center gap-3 py-14 px-6 text-center"
        data-testid="abschluss-no-incident"
      >
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
          <FileCheck2 className="h-6 w-6" />
        </div>
        <h3 className="text-heading">Kein aktiver Incident</h3>
        <p className="text-caption text-muted-foreground max-w-md">
          Waehle oder starte zunaechst einen Incident, um die Auswertung und den
          Abschlussbericht einzusehen.
        </p>
        <Button
          size="sm"
          onClick={() => navigate('/')}
          data-testid="abschluss-goto-incidents"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Zu den Incidents
        </Button>
      </div>
    </div>
  );
}

/* ====================================================================
   ABSCHLUSS-CHECK Tab
==================================================================== */
function AbschlussCheckTab({
  check,
  loading,
  onRefresh,
  onFreigabe,
  canFreigabe,
  incident,
}) {
  if (loading || !check) {
    return (
      <div className="els-surface h-40 animate-pulse bg-surface-raised/60" />
    );
  }

  const bereit = check.bereit_fuer_abschluss;
  const alreadyClosed = incident?.status === 'abgeschlossen';

  return (
    <div className="space-y-4" data-testid="abschluss-check">
      <div
        className={
          'els-surface flex items-start gap-3 p-4 ' +
          (alreadyClosed
            ? 'border-status-gray/50'
            : bereit
              ? 'border-status-green/50 bg-status-green/5'
              : 'border-status-red/50 bg-status-red/5')
        }
      >
        {alreadyClosed ? (
          <Lock className="h-5 w-5 text-status-gray mt-0.5" />
        ) : bereit ? (
          <CheckCircle2 className="h-5 w-5 text-status-green mt-0.5" />
        ) : (
          <XCircle className="h-5 w-5 text-status-red mt-0.5" />
        )}
        <div className="flex-1">
          <div className="text-heading">
            {alreadyClosed
              ? 'Incident bereits abgeschlossen'
              : bereit
                ? 'Bereit fuer Abschluss'
                : 'Noch nicht bereit'}
          </div>
          <p className="text-caption text-muted-foreground mt-0.5">
            {alreadyClosed
              ? `Abgeschlossen am ${fmtDT(incident?.end_at)}.`
              : bereit
                ? 'Keine Blocker mehr. Du kannst den Incident jetzt freigeben und schliessen.'
                : `${check.blockers.length} Blocker muessen beseitigt sein.`}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={onRefresh}
          data-testid="abschluss-check-refresh"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Neu pruefen
        </Button>
        {bereit && !alreadyClosed && (
          <Button
            size="sm"
            onClick={onFreigabe}
            disabled={!canFreigabe}
            data-testid="abschluss-freigabe-btn"
            title={canFreigabe ? 'Incident abschliessen' : 'Nur Einsatzleiter'}
          >
            <FileCheck2 className="h-3.5 w-3.5" />
            Freigeben & Abschliessen
          </Button>
        )}
      </div>

      <SectionCard
        title="Blocker"
        subtitle="Muessen vor Abschluss beseitigt sein"
        testId="abschluss-blockers"
      >
        {check.blockers.length === 0 ? (
          <div className="text-caption text-muted-foreground">
            Keine Blocker.
          </div>
        ) : (
          <ul className="space-y-2">
            {check.blockers.map((b) => (
              <li
                key={b.id}
                className="flex items-start gap-3 rounded-md border border-status-red/30 bg-status-red/10 p-3"
                data-testid={`blocker-${b.id}`}
              >
                <XCircle className="h-4 w-4 text-status-red mt-0.5 shrink-0" />
                <div className="flex-1">
                  <div className="text-body font-medium text-status-red">
                    {b.titel}
                  </div>
                  <p className="text-caption text-muted-foreground">
                    {b.beschreibung}
                  </p>
                </div>
                <StatusBadge tone="red" variant="soft" size="sm">
                  Blocker
                </StatusBadge>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      <SectionCard
        title="Warnungen"
        subtitle="Empfohlen vor Abschluss zu klaeren"
        testId="abschluss-warnings"
      >
        {check.warnings.length === 0 ? (
          <div className="text-caption text-muted-foreground">
            Keine Warnungen.
          </div>
        ) : (
          <ul className="space-y-2">
            {check.warnings.map((w) => (
              <li
                key={w.id}
                className="flex items-start gap-3 rounded-md border border-status-yellow/30 bg-status-yellow/10 p-3"
                data-testid={`warning-${w.id}`}
              >
                <AlertTriangle className="h-4 w-4 text-status-yellow mt-0.5 shrink-0" />
                <div className="flex-1">
                  <div className="text-body font-medium text-status-yellow">
                    {w.titel}
                  </div>
                  <p className="text-caption text-muted-foreground">
                    {w.beschreibung}
                  </p>
                </div>
                <StatusBadge tone="yellow" variant="soft" size="sm">
                  Warnung
                </StatusBadge>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>
    </div>
  );
}

/* ====================================================================
   BERICHTSVORSCHAU Tab  (A4-Optik, druckbar)
==================================================================== */
function ReportDocument({ report }) {
  const inc = report.incident;
  const k = Object.fromEntries(report.kapitel.map((x) => [x.nr, x]));

  return (
    <article className="report-a4" data-testid="report-a4">
      {/* Kopf */}
      <div className="flex items-center justify-between border-b-2 border-slate-700 pb-2 mb-3">
        <div>
          <div className="text-[9pt] uppercase tracking-[0.2em] text-slate-500">
            Einsatzleitsystem Malteser Hilfsdienst
          </div>
          <h1>Einsatzbericht</h1>
        </div>
        <div className="text-right text-[9pt] text-slate-500">
          Generiert am
          <br />
          <span className="font-mono text-slate-800">
            {fmtDT(report.generiert_at)}
          </span>
        </div>
      </div>

      {/* 1 Grunddaten */}
      <section className="kap">
        <h2>1. Einsatzgrunddaten</h2>
        <dl className="kv">
          <dt>Name</dt>
          <dd>{inc.name}</dd>
          <dt>Typ</dt>
          <dd>{inc.typ}</dd>
          <dt>Ort</dt>
          <dd>{inc.ort || '–'}</dd>
          <dt>Beginn</dt>
          <dd>{fmtDT(inc.start_at)}</dd>
          <dt>Ende</dt>
          <dd>{fmtDT(inc.end_at)}</dd>
          <dt>Einsatzdauer</dt>
          <dd>{k[1].inhalt.dauer_min} min</dd>
          <dt>Status</dt>
          <dd>
            <span className="pill">{inc.status}</span>
            {inc.demo && (
              <span className="pill pill-yellow" style={{ marginLeft: 4 }}>
                DEMO
              </span>
            )}
          </dd>
        </dl>
      </section>

      {/* 2 Rollen */}
      <section className="kap">
        <h2>2. Organisation & Rollen</h2>
        <p>Rollen im Einsatz: {k[2].inhalt.rollen.join(' · ')}</p>
      </section>

      {/* 3 Patientenuebersicht */}
      <section className="kap">
        <h2>3. Patientenuebersicht</h2>
        <dl className="kv">
          <dt>Gesamt</dt>
          <dd>{k[3].inhalt.total}</dd>
          <dt>S1 · sofort</dt>
          <dd>
            <span className="pill pill-red">{k[3].inhalt.sichtung.S1}</span>
          </dd>
          <dt>S2 · dringend</dt>
          <dd>
            <span className="pill pill-yellow">{k[3].inhalt.sichtung.S2}</span>
          </dd>
          <dt>S3 · normal</dt>
          <dd>
            <span className="pill pill-green">{k[3].inhalt.sichtung.S3}</span>
          </dd>
          <dt>S0 · leicht</dt>
          <dd>
            <span className="pill pill-gray">{k[3].inhalt.sichtung.S0}</span>
          </dd>
        </dl>
      </section>

      {/* 4 Patientenliste */}
      <section className="kap">
        <h2>4. Patientenliste</h2>
        <table>
          <thead>
            <tr>
              <th>Kennung</th>
              <th>Sichtung</th>
              <th>Status</th>
              <th>Verbleib</th>
              <th>Notiz</th>
            </tr>
          </thead>
          <tbody>
            {k[4].inhalt.patienten.length === 0 && (
              <tr>
                <td
                  colSpan={5}
                  style={{ textAlign: 'center', color: '#64748b' }}
                >
                  Keine Patienten erfasst
                </td>
              </tr>
            )}
            {k[4].inhalt.patienten.map((p) => (
              <tr key={p.id}>
                <td style={{ fontFamily: 'monospace' }}>{p.kennung}</td>
                <td>
                  <span
                    className={
                      'pill ' +
                      (p.sichtung === 'S1'
                        ? 'pill-red'
                        : p.sichtung === 'S2'
                          ? 'pill-yellow'
                          : p.sichtung === 'S3'
                            ? 'pill-green'
                            : 'pill-gray')
                    }
                  >
                    {p.sichtung || '–'}
                  </span>
                </td>
                <td>{STATUS_LABEL[p.status] || p.status}</td>
                <td>{p.verbleib || '–'}</td>
                <td>{p.notiz || '–'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* 6 Zeiten */}
      <section className="kap">
        <h2>5. Behandlungszeiten</h2>
        <dl className="kv">
          <dt>Ø Wartezeit</dt>
          <dd>{fmtMin(k[6].inhalt.wartezeit_min_avg)}</dd>
          <dt>Ø Behandlungsdauer</dt>
          <dd>{fmtMin(k[6].inhalt.behandlungsdauer_min_avg)}</dd>
        </dl>
      </section>

      {/* 7 Transporte */}
      <section className="kap">
        <h2>6. Transporte</h2>
        <dl className="kv">
          <dt>Gesamt</dt>
          <dd>{k[7].inhalt.summary.total}</dd>
          <dt>intern / extern</dt>
          <dd>
            {k[7].inhalt.summary.typ.intern} / {k[7].inhalt.summary.typ.extern}
          </dd>
          <dt>Ø Fahrtdauer</dt>
          <dd>{fmtMin(k[7].inhalt.summary.fahrtdauer_min_avg)}</dd>
        </dl>
        {k[7].inhalt.transporte.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>Patient</th>
                <th>Typ</th>
                <th>Ziel</th>
                <th>Ressource</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {k[7].inhalt.transporte.map((t) => (
                <tr key={t.id}>
                  <td style={{ fontFamily: 'monospace' }}>
                    {t.patient_kennung || '–'}
                  </td>
                  <td>{t.typ}</td>
                  <td>{t.ziel}</td>
                  <td>{t.ressource || '–'}</td>
                  <td>{TRANSPORT_STATUS_LABEL[t.status] || t.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* 8 Ressourcen */}
      <section className="kap">
        <h2>7. Ressourcen</h2>
        <dl className="kv">
          <dt>Gesamt</dt>
          <dd>{k[8].inhalt.summary.total}</dd>
          <dt>Verfuegbar / im Einsatz</dt>
          <dd>
            {k[8].inhalt.summary.status.verfuegbar} /{' '}
            {k[8].inhalt.summary.status.im_einsatz}
          </dd>
        </dl>
      </section>

      {/* 9 Meldungen */}
      <section className="kap">
        <h2>8. Kommunikation</h2>
        <dl className="kv">
          <dt>Gesamt</dt>
          <dd>{k[9].inhalt.summary.total}</dd>
          <dt>Offen</dt>
          <dd>{k[9].inhalt.summary.offen}</dd>
          <dt>Ø Quittierdauer</dt>
          <dd>{fmtMin(k[9].inhalt.summary.quittier_dauer_min_avg)}</dd>
        </dl>
      </section>

      {/* 10 Konflikte */}
      <section className="kap">
        <h2>9. Konflikte & Blocker</h2>
        <p>
          <span className="pill pill-red">{k[10].inhalt.rot} rot</span>{' '}
          <span className="pill pill-yellow">{k[10].inhalt.gelb} gelb</span> von
          insgesamt {k[10].inhalt.total} Konflikten.
        </p>
      </section>

      {/* 11 Besondere Vorkommnisse */}
      <section className="kap">
        <h2>10. Besondere Vorkommnisse</h2>
        <p style={{ whiteSpace: 'pre-wrap' }}>{k[11].inhalt.text || '—'}</p>
      </section>

      {/* 12 Nachbearbeitung */}
      <section className="kap">
        <h2>11. Nachbearbeitung & Anmerkungen</h2>
        <p style={{ whiteSpace: 'pre-wrap' }}>{k[12].inhalt.text || '—'}</p>
      </section>

      {/* 13 Freigabe */}
      <section className="kap">
        <h2>12. Freigabe</h2>
        <dl className="kv">
          <dt>Status</dt>
          <dd>
            {k[13].inhalt.bereit_fuer_abschluss ? 'Freigegeben' : 'Ausstehend'}
          </dd>
          <dt>Freigegeben von</dt>
          <dd>{k[13].inhalt.freigegeben_von || '—'}</dd>
          <dt>Freigabe am</dt>
          <dd>{fmtDT(k[13].inhalt.freigabe_at)}</dd>
        </dl>
      </section>

      {/* 14 */}
      <section className="kap">
        <h2>13. Anhaenge & Quellen</h2>
        <p>{k[14].inhalt.quellen}</p>
        <p className="text-[8.5pt] text-slate-500 mt-2">
          Generiert am {fmtDT(k[14].inhalt.generiert_at)}
        </p>
      </section>
    </article>
  );
}

function ReportPreviewTab({ report, loading, onPrint, canExport }) {
  if (loading || !report) {
    return (
      <div className="els-surface h-96 animate-pulse bg-surface-raised/60" />
    );
  }

  return (
    <div className="space-y-4" data-testid="abschluss-report">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 no-print">
        <div>
          <div className="text-caption uppercase tracking-wider text-muted-foreground">
            Vorschau
          </div>
          <div className="text-heading">Einsatzbericht (A4)</div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={onPrint}
            disabled={!canExport}
            data-testid="report-print-btn"
            title={
              canExport ? 'Drucken / als PDF speichern' : 'Keine Berechtigung'
            }
          >
            <Printer className="h-3.5 w-3.5" />
            Drucken / PDF
          </Button>
        </div>
      </div>

      {/* A4 Preview */}
      <div className="print-area overflow-auto bg-neutral-900/40 p-4 rounded-md">
        <ReportDocument report={report} />
      </div>
    </div>
  );
}

/* ====================================================================
   NACHBEARBEITUNG Tab
==================================================================== */
function NachbearbeitungTab({ incident, canEdit, onSaved }) {
  const [besondere, setBesondere] = React.useState(
    incident?.meta?.besondere_vorkommnisse || '',
  );
  const [nach, setNach] = React.useState(incident?.meta?.nachbearbeitung || '');
  const [saving, setSaving] = React.useState(false);

  React.useEffect(() => {
    setBesondere(incident?.meta?.besondere_vorkommnisse || '');
    setNach(incident?.meta?.nachbearbeitung || '');
  }, [incident]);

  const handleSave = async () => {
    if (!canEdit) return;
    setSaving(true);
    try {
      await patchIncidentMeta(incident.id, {
        besondere_vorkommnisse: besondere,
        nachbearbeitung: nach,
      });
      toast.success('Nachbearbeitung gespeichert');
      onSaved?.();
    } catch (e) {
      toast.error('Speichern fehlgeschlagen');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4" data-testid="abschluss-nachbearbeitung">
      <SectionCard title="Besondere Vorkommnisse" subtitle="Freitext">
        <Textarea
          value={besondere}
          onChange={(e) => setBesondere(e.target.value)}
          rows={5}
          disabled={!canEdit}
          placeholder="z.B. Grossschadenslage MANV, Umleitung wegen Gewitter, Pressekontakt …"
          data-testid="meta-besondere"
          className="bg-background"
        />
      </SectionCard>
      <SectionCard title="Nachbearbeitung & Anmerkungen" subtitle="Freitext">
        <Textarea
          value={nach}
          onChange={(e) => setNach(e.target.value)}
          rows={6}
          disabled={!canEdit}
          placeholder="Lessons Learned, offene Themen, Empfehlungen …"
          data-testid="meta-nachbearbeitung"
          className="bg-background"
        />
      </SectionCard>
      <div className="flex justify-end">
        <Button
          onClick={handleSave}
          disabled={!canEdit || saving}
          data-testid="meta-save-btn"
        >
          <Save className="h-3.5 w-3.5" />
          {saving ? 'Speichere…' : 'Speichern'}
        </Button>
      </div>
    </div>
  );
}

/* ====================================================================
   VERSIONEN Tab
==================================================================== */
function VersionenTab({ versions, loading, onCreate, canCreate, onRefresh }) {
  return (
    <div className="space-y-4" data-testid="abschluss-versionen">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-caption uppercase tracking-wider text-muted-foreground">
            Bericht
          </div>
          <div className="text-heading">Versionen</div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={onRefresh}
            data-testid="versions-refresh"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Neu laden
          </Button>
          <Button
            size="sm"
            onClick={onCreate}
            disabled={!canCreate}
            data-testid="version-create-btn"
            title={canCreate ? 'Snapshot erstellen' : 'Nur Einsatzleiter'}
          >
            <History className="h-3.5 w-3.5" />
            Version erstellen
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="els-surface h-32 animate-pulse bg-surface-raised/60" />
      ) : versions.length === 0 ? (
        <div className="els-surface p-6 text-center text-caption text-muted-foreground">
          Noch keine Versionen. Erstelle eine Momentaufnahme des Berichts.
        </div>
      ) : (
        <ul className="space-y-2">
          {versions.map((v) => (
            <li
              key={v.id}
              className="els-surface flex items-center gap-3 p-3"
              data-testid={`version-${v.version}`}
            >
              <FileText className="h-4 w-4 text-primary" />
              <div className="flex-1 min-w-0">
                <div className="text-body font-medium">Version {v.version}</div>
                <div className="text-caption text-muted-foreground truncate">
                  {v.freigegeben_von} · {fmtDT(v.created_at)}
                  {v.kommentar ? ` · ${v.kommentar}` : ''}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/* ====================================================================
   PAGE
==================================================================== */
export default function AbschlussPage() {
  const navigate = useNavigate();
  const {
    activeIncident,
    closeIncident,
    refresh: refreshIncidents,
  } = useIncidents();
  const { can, roleMeta } = useRole();

  const [tab, setTab] = React.useState('check');
  const [check, setCheck] = React.useState(null);
  const [report, setReport] = React.useState(null);
  const [versions, setVersions] = React.useState([]);
  const [loading, setLoading] = React.useState({
    check: false,
    report: false,
    versions: false,
  });
  const [confirmFreigabe, setConfirmFreigabe] = React.useState(false);

  const incidentId = activeIncident?.id;
  const isArchived = activeIncident?.status === 'abgeschlossen';

  // Default-Tab: fuer Archiv "bericht", sonst "check"
  const [tabSet, setTabSet] = React.useState(false);
  React.useEffect(() => {
    if (tabSet) return;
    setTab(isArchived ? 'bericht' : 'check');
    setTabSet(true);
  }, [isArchived, tabSet]);

  const loadCheck = React.useCallback(async () => {
    if (!incidentId) return;
    setLoading((l) => ({ ...l, check: true }));
    try {
      setCheck(await getAbschlussCheck(incidentId));
    } catch (e) {
      toast.error('Abschluss-Check fehlgeschlagen');
    } finally {
      setLoading((l) => ({ ...l, check: false }));
    }
  }, [incidentId]);

  const loadReport = React.useCallback(async () => {
    if (!incidentId) return;
    setLoading((l) => ({ ...l, report: true }));
    try {
      setReport(await getReport(incidentId));
    } catch (e) {
      toast.error('Bericht konnte nicht geladen werden');
    } finally {
      setLoading((l) => ({ ...l, report: false }));
    }
  }, [incidentId]);

  const loadVersions = React.useCallback(async () => {
    if (!incidentId) return;
    setLoading((l) => ({ ...l, versions: true }));
    try {
      setVersions(await listReportVersions(incidentId));
    } catch (e) {
      toast.error('Versionen konnten nicht geladen werden');
    } finally {
      setLoading((l) => ({ ...l, versions: false }));
    }
  }, [incidentId]);

  React.useEffect(() => {
    if (!incidentId) return;
    loadCheck();
    loadReport();
    loadVersions();
  }, [incidentId, loadCheck, loadReport, loadVersions]);

  if (!activeIncident) return <NoIncidentState />;

  const handleFreigabe = async () => {
    try {
      await patchIncidentMeta(incidentId, {});
      // Meta-Patch alleine reicht nicht – wir setzen freigabe-Felder serverseitig
      // via createReportVersion (erzeugt Snapshot + markiert Freigabe).
      await createReportVersion(incidentId, {
        freigegeben_von: roleMeta?.label || 'Einsatzleiter',
        kommentar: 'Freigabe & Abschluss',
      });
      await closeIncident(incidentId);
      await refreshIncidents();
      await loadCheck();
      await loadReport();
      await loadVersions();
      toast.success('Incident erfolgreich abgeschlossen');
    } catch (e) {
      toast.error('Freigabe fehlgeschlagen');
    } finally {
      setConfirmFreigabe(false);
    }
  };

  const handleCreateVersion = async () => {
    try {
      await createReportVersion(incidentId, {
        freigegeben_von: roleMeta?.label || 'Einsatzleiter',
        kommentar: 'Snapshot',
      });
      toast.success('Version erstellt');
      await loadVersions();
    } catch (e) {
      toast.error('Version konnte nicht erstellt werden');
    }
  };

  const handlePrint = () => {
    setTab('bericht');
    setTimeout(() => window.print(), 200);
  };

  return (
    <div className="mx-auto w-full max-w-[1400px] px-6 py-6">
      {/* Kopf */}
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="text-caption uppercase tracking-wider text-muted-foreground">
            Schritt 09 · Auswertung & Abschluss
          </div>
          <h1 className="mt-1 text-display" data-testid="abschluss-title">
            Abschluss & Bericht
          </h1>
          <p className="mt-1 max-w-2xl text-body text-muted-foreground">
            Dashboard-KPIs, Abschluss-Check, A4-Berichtsvorschau,
            Nachbearbeitung und Versionierung – alles fuer ein sauberes
            Einsatzende.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => navigate('/lage')}
          data-testid="abschluss-back"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Zur Lage
        </Button>
      </div>

      <Tabs value={tab} onValueChange={setTab} data-testid="abschluss-tabs">
        <TabsList className="bg-surface-sunken">
          {!isArchived && (
            <TabsTrigger value="check" data-testid="tab-check">
              Abschluss-Check
              {check && check.blockers.length > 0 && (
                <StatusBadge
                  tone="red"
                  variant="solid"
                  size="sm"
                  className="ml-2"
                >
                  {check.blockers.length}
                </StatusBadge>
              )}
            </TabsTrigger>
          )}
          <TabsTrigger value="bericht" data-testid="tab-bericht">
            Berichtsvorschau
          </TabsTrigger>
          <TabsTrigger value="versionen" data-testid="tab-versionen">
            Versionen
            {versions.length > 0 && (
              <StatusBadge
                tone="neutral"
                variant="soft"
                size="sm"
                className="ml-2"
              >
                {versions.length}
              </StatusBadge>
            )}
          </TabsTrigger>
          {!isArchived && (
            <TabsTrigger value="meta" data-testid="tab-meta">
              Nachbearbeitung
            </TabsTrigger>
          )}
        </TabsList>

        <div className="mt-4">
          {!isArchived && (
            <TabsContent value="check">
              <AbschlussCheckTab
                check={check}
                loading={loading.check}
                onRefresh={() => {
                  loadCheck();
                }}
                onFreigabe={() => setConfirmFreigabe(true)}
                canFreigabe={can('abschluss.freigabe')}
                incident={activeIncident}
              />
            </TabsContent>
          )}
          <TabsContent value="bericht">
            <ReportPreviewTab
              report={report}
              loading={loading.report}
              onPrint={handlePrint}
              canExport={can('abschluss.export_pdf')}
            />
          </TabsContent>
          <TabsContent value="versionen">
            <VersionenTab
              versions={versions}
              loading={loading.versions}
              onCreate={handleCreateVersion}
              canCreate={can('abschluss.version_create') && !isArchived}
              onRefresh={loadVersions}
            />
          </TabsContent>
          {!isArchived && (
            <TabsContent value="meta">
              <NachbearbeitungTab
                incident={activeIncident}
                canEdit={can('abschluss.edit_meta')}
                onSaved={() => {
                  loadReport();
                  refreshIncidents();
                }}
              />
            </TabsContent>
          )}
        </div>
      </Tabs>

      {/* Druck-Area (nur sichtbar beim Drucken via @media print) */}
      {report && (
        <div className="hidden print:block print-area">
          <ReportDocument report={report} />
        </div>
      )}

      <ConfirmModal
        open={confirmFreigabe}
        onOpenChange={setConfirmFreigabe}
        title="Incident freigeben & abschliessen?"
        description="Der Incident wird abgeschlossen, eine Bericht-Version wird erzeugt und alle Daten werden fuer die Dokumentation eingefroren. Diese Aktion kann rueckgaengig gemacht werden (Wiedereroeffnen)."
        confirmLabel="Freigeben & Abschliessen"
        onConfirm={handleFreigabe}
      />
    </div>
  );
}
