import * as React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  StatusBadge,
  SichtungBadge,
  KpiTile,
  SectionCard,
  ConfirmModal,
} from '@/components/primitives';
import { PatientTimeline } from '@/components/patients/PatientTimeline';
import {
  TransportChoiceDialog,
  FallabschlussChoiceDialog,
} from '@/components/patients/ChoiceDialogs';
import { usePatients } from '@/context/PatientContext';
import { useTransports } from '@/context/TransportContext';
import { useIncidents } from '@/context/IncidentContext';
import { useRole } from '@/context/RoleContext';
import {
  listBetten,
  listAbschnitte,
  listResources,
  assignBett,
  releaseBett,
} from '@/lib/api';
import { getFarbe } from '@/lib/abschnitt-meta';
import {
  ArrowLeft,
  ArrowRight,
  Trash2,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  Truck,
  FileCheck2,
  Bed,
  UserMinus,
  RotateCcw,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatDuration } from '@/lib/time';
import {
  SICHTUNG,
  PATIENT_STATUS,
  PATIENT_VERBLEIB,
  TRANSPORT_TYP,
  FALLABSCHLUSS_TYP,
  VERBLEIB_OPTIONS,
  nextProgression,
} from '@/lib/patient-meta';
import { getPatient as apiGetPatient } from '@/lib/api';

function useDebouncedEffect(callback, deps, delay) {
  React.useEffect(() => {
    const id = setTimeout(callback, delay);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, delay]);
}

function SichtungGrid({ value, onSelect, disabled }) {
  return (
    <div className="grid grid-cols-4 gap-2">
      {SICHTUNG.map((s) => {
        const active = value === s.key;
        return (
          <button
            key={s.key}
            type="button"
            disabled={disabled}
            onClick={() => onSelect(s.key)}
            data-testid={`pd-sichtung-${s.key}`}
            className={cn(
              'flex h-16 flex-col items-center justify-center rounded-md border font-semibold transition-colors disabled:opacity-60',
              active &&
                s.tone === 'red' &&
                'bg-status-red text-status-red-fg border-status-red',
              active &&
                s.tone === 'yellow' &&
                'bg-status-yellow text-status-yellow-fg border-status-yellow',
              active &&
                s.tone === 'green' &&
                'bg-status-green text-status-green-fg border-status-green',
              active &&
                s.tone === 'gray' &&
                'bg-status-gray text-status-gray-fg border-status-gray',
              !active &&
                'border-border text-foreground hover:bg-surface-raised',
            )}
          >
            <span className="font-mono text-display leading-none">{s.key}</span>
            <span className="text-[0.65rem] uppercase tracking-wider opacity-80">
              {s.hint}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function Prozesszeiten({ patient }) {
  const [now, setNow] = React.useState(Date.now());
  React.useEffect(() => {
    const closed =
      patient.status === 'uebergeben' || patient.status === 'entlassen';
    if (closed) return undefined;
    const id = setInterval(() => setNow(Date.now()), 30 * 1000);
    return () => clearInterval(id);
  }, [patient.status]);

  const end =
    patient.fallabschluss_at != null
      ? new Date(patient.fallabschluss_at).getTime()
      : now;

  const seitSichtung = patient.sichtung_at
    ? end - new Date(patient.sichtung_at).getTime()
    : null;

  const behandlungsdauer = patient.behandlung_start_at
    ? (patient.transport_angefordert_at
        ? new Date(patient.transport_angefordert_at).getTime()
        : end) - new Date(patient.behandlung_start_at).getTime()
    : null;

  const transportdauer = patient.transport_angefordert_at
    ? (patient.fallabschluss_at
        ? new Date(patient.fallabschluss_at).getTime()
        : now) - new Date(patient.transport_angefordert_at).getTime()
    : null;

  return (
    <div className="grid grid-cols-3 gap-2">
      <KpiTile
        label="Seit Sichtung"
        value={seitSichtung != null ? formatDuration(seitSichtung) : '–'}
        tone="default"
        testId="kpi-seit-sichtung"
      />
      <KpiTile
        label="Behandlungsdauer"
        value={
          behandlungsdauer != null ? formatDuration(behandlungsdauer) : '–'
        }
        tone={behandlungsdauer != null ? 'green' : 'gray'}
        testId="kpi-behandlung"
      />
      <KpiTile
        label="Seit Transport-Anforderung"
        value={transportdauer != null ? formatDuration(transportdauer) : '–'}
        tone={transportdauer != null ? 'yellow' : 'gray'}
        testId="kpi-transport"
      />
    </div>
  );
}

export default function PatientDetail() {
  const { patientId } = useParams();
  const navigate = useNavigate();
  const { activeIncident, setActive } = useIncidents();
  const { patients, update, remove, refresh, reopen } = usePatients();
  const { refresh: refreshTransports } = useTransports();

  const [reopenOpen, setReopenOpen] = React.useState(false);

  const [patient, setPatient] = React.useState(
    () => patients.find((p) => p.id === patientId) || null,
  );
  const [loading, setLoading] = React.useState(!patient);
  const [notiz, setNotiz] = React.useState(patient?.notiz || '');
  const [verbleib, setVerbleib] = React.useState(
    patient?.verbleib || 'unbekannt',
  );
  const [transportOpen, setTransportOpen] = React.useState(false);
  const [abschlussOpen, setAbschlussOpen] = React.useState(false);
  const [deleteOpen, setDeleteOpen] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [notizSaved, setNotizSaved] = React.useState(true);
  const [error, setError] = React.useState(null);
  const [betten, setBetten] = React.useState([]);
  const [abschnitte, setAbschnitte] = React.useState([]);
  const [resources, setResources] = React.useState([]);
  const [bettModalOpen, setBettModalOpen] = React.useState(false);
  const { can } = useRole();

  // Betten, Abschnitte und Ressourcen fuer Zuweisungs-UI laden
  React.useEffect(() => {
    if (!activeIncident?.id) return;
    let cancelled = false;
    (async () => {
      try {
        const [b, a, r] = await Promise.all([
          listBetten(activeIncident.id),
          listAbschnitte(activeIncident.id),
          listResources(activeIncident.id),
        ]);
        if (!cancelled) {
          setBetten(b);
          setAbschnitte(a);
          setResources(r);
        }
      } catch {
        /* silent */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeIncident?.id, patient?.bett_id]);

  const availableTreatmentResources = React.useMemo(
    () =>
      resources
        .filter((r) => r.status !== 'offline')
        .sort((a, b) => a.name.localeCompare(b.name, 'de')),
    [resources],
  );

  const currentTreatmentResourceLabel = React.useMemo(() => {
    if (!patient?.behandlung_ressource_id) return null;
    const fromList = resources.find(
      (r) => r.id === patient.behandlung_ressource_id,
    );
    return fromList?.name || patient.behandlung_ressource_name || null;
  }, [patient, resources]);

  const currentBett = React.useMemo(() => {
    if (!patient?.bett_id) return null;
    return betten.find((b) => b.id === patient.bett_id) || null;
  }, [betten, patient?.bett_id]);

  const abschnittById = React.useMemo(() => {
    const m = new Map();
    for (const a of abschnitte) m.set(a.id, a);
    return m;
  }, [abschnitte]);

  const handleAssignBett = async (bettId) => {
    try {
      await assignBett(bettId, patient.id);
      await refresh();
      const b = await listBetten(activeIncident.id);
      setBetten(b);
      setBettModalOpen(false);
    } catch (e) {
      // noop
    }
  };

  const handleReleaseBett = async () => {
    if (!currentBett) return;
    try {
      await releaseBett(currentBett.id);
      await refresh();
      const b = await listBetten(activeIncident.id);
      setBetten(b);
    } catch (e) {
      // noop
    }
  };

  // Sync aus Liste (z.B. nach refresh)
  React.useEffect(() => {
    const fromList = patients.find((p) => p.id === patientId);
    if (fromList) {
      setPatient(fromList);
      setNotiz((n) =>
        n === (fromList.notiz || '') ? n : fromList.notiz || '',
      );
      setVerbleib(fromList.verbleib || 'unbekannt');
    }
  }, [patients, patientId]);

  // Wenn nicht in Liste, direkt vom Backend holen (Deep-Link-Fall)
  React.useEffect(() => {
    let cancelled = false;
    async function load() {
      if (patient) {
        setLoading(false);
        return;
      }
      try {
        const p = await apiGetPatient(patientId);
        if (cancelled) return;
        setPatient(p);
        setNotiz(p.notiz || '');
        setVerbleib(p.verbleib || 'unbekannt');
        // Stelle sicher, dass Incident aktiv ist
        if (p.incident_id && activeIncident?.id !== p.incident_id) {
          setActive(p.incident_id);
        }
      } catch (e) {
        if (!cancelled) setError('Patient nicht gefunden.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [patientId]);

  // Debounced Notiz-Save
  useDebouncedEffect(
    async () => {
      if (!patient) return;
      if ((patient.notiz || '') === notiz) return;
      setNotizSaved(false);
      try {
        const updated = await update(patient.id, { notiz });
        setPatient(updated);
        setNotizSaved(true);
      } catch {
        setNotizSaved(false);
      }
    },
    [notiz],
    800,
  );

  const applyPatch = React.useCallback(
    async (patch, { silent = false } = {}) => {
      if (!patient) return;
      setBusy(true);
      setError(null);
      try {
        const updated = await update(patient.id, patch);
        if (
          Object.prototype.hasOwnProperty.call(patch, 'transport_typ') ||
          Object.prototype.hasOwnProperty.call(patch, 'status') ||
          Object.prototype.hasOwnProperty.call(patch, 'fallabschluss_typ')
        ) {
          await refreshTransports();
        }
        setPatient(updated);
        return updated;
      } catch (e) {
        if (!silent)
          setError(
            e?.response?.data?.detail ||
              e?.message ||
              'Aktualisierung fehlgeschlagen',
          );
        throw e;
      } finally {
        setBusy(false);
      }
    },
    [patient, refreshTransports, update],
  );

  const handleSichtung = (k) => applyPatch({ sichtung: k });

  const handleVerbleibChange = async (v) => {
    setVerbleib(v);
    try {
      await applyPatch({ verbleib: v }, { silent: true });
    } catch {
      /* noop, error state set */
    }
  };

  const handleTransport = (typ) => applyPatch({ transport_typ: typ });
  const handleAbschluss = (typ) => applyPatch({ fallabschluss_typ: typ });

  const handleTreatmentResourceChange = async (value) => {
    const patch = {
      behandlung_ressource_id: value === 'none' ? null : value,
    };
    await applyPatch(patch);
  };

  const handleReopen = async () => {
    if (!patient) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await reopen(patient.id);
      await refreshTransports();
      setPatient(updated);
      setVerbleib(updated.verbleib || 'unbekannt');
    } catch (e) {
      setError(
        e?.response?.data?.detail ||
          e?.message ||
          'Wiedereroeffnung fehlgeschlagen',
      );
    } finally {
      setBusy(false);
      setReopenOpen(false);
    }
  };

  const next = patient ? nextProgression(patient) : null;

  const handleNext = async () => {
    if (!next) return;
    if (next.type === 'require-sichtung') {
      // Fokussiere die Sichtungs-Grid-Buttons
      document.querySelector('[data-testid="pd-sichtung-S1"]')?.focus();
      return;
    }
    if (next.type === 'set-status') {
      await applyPatch(next.payload);
      return;
    }
    if (next.type === 'ask-transport') {
      setTransportOpen(true);
      return;
    }
    if (next.type === 'ask-fallabschluss') {
      setAbschlussOpen(true);
    }
  };

  const handleDelete = async () => {
    if (!patient) return;
    await remove(patient.id);
    await refreshTransports();
    navigate('/patienten');
  };

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error && !patient) {
    return (
      <div className="mx-auto max-w-xl p-6">
        <div
          className="els-surface p-6 text-center"
          data-testid="patient-detail-error"
        >
          <AlertTriangle className="mx-auto h-8 w-8 text-status-red" />
          <h2 className="mt-3 text-display">Patient nicht gefunden</h2>
          <p className="mt-1 text-muted-foreground">{error}</p>
          <Button className="mt-4" onClick={() => navigate('/patienten')}>
            <ArrowLeft className="h-4 w-4" />
            Zurueck zur Liste
          </Button>
        </div>
      </div>
    );
  }

  if (!patient) return null;

  const statusMeta = PATIENT_STATUS[patient.status] || {
    label: patient.status,
    tone: 'neutral',
  };
  const closed =
    patient.status === 'uebergeben' || patient.status === 'entlassen';

  return (
    <div className="mx-auto w-full max-w-[1400px] px-6 py-6">
      {/* Kopfzeile */}
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate('/patienten')}
            data-testid="pd-back"
            className="mt-1"
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <div className="text-caption uppercase tracking-wider text-muted-foreground">
              Schritt 04 · Patientendetail
            </div>
            <h1
              className="font-mono text-display mt-1"
              data-testid="pd-kennung"
            >
              {patient.kennung}
            </h1>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              {patient.sichtung ? (
                <SichtungBadge level={patient.sichtung} />
              ) : (
                <StatusBadge tone="neutral" variant="outline" size="sm">
                  Sichtung offen
                </StatusBadge>
              )}
              <StatusBadge
                tone={statusMeta.tone}
                variant="soft"
                size="sm"
                dot={!closed}
                data-testid="pd-status"
              >
                {statusMeta.label}
              </StatusBadge>
              {activeIncident?.demo && (
                <StatusBadge tone="yellow" variant="solid" size="sm">
                  DEMO
                </StatusBadge>
              )}
              <span className="text-caption text-muted-foreground">
                {activeIncident?.name}
              </span>
            </div>
          </div>
        </div>

        {/* Ein-Klick-Progression */}
        <div className="flex flex-col items-end gap-1">
          {next ? (
            <Button
              size="lg"
              onClick={handleNext}
              disabled={busy}
              data-testid="pd-next-step"
              className="h-12 px-5"
            >
              {busy ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <ArrowRight className="h-4 w-4" />
              )}
              {next.label}
            </Button>
          ) : (
            <div
              className="flex items-center gap-2 rounded-md border border-status-green/40 bg-status-green/10 px-3 py-2 text-status-green"
              data-testid="pd-done"
            >
              <CheckCircle2 className="h-4 w-4" />
              <span className="font-medium">
                {PATIENT_STATUS[patient.status]?.label}
              </span>
            </div>
          )}
          {next?.description && (
            <span className="text-caption text-muted-foreground">
              {next.description}
            </span>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-3 rounded-md border border-status-red/40 bg-status-red/10 px-3 py-2 text-caption text-status-red">
          {error}
        </div>
      )}

      {/* Prozesszeiten */}
      <div className="mb-4">
        <Prozesszeiten patient={patient} />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.2fr_1fr]">
        {/* Linke Spalte: Erfassung */}
        <div className="space-y-4">
          <SectionCard
            title="Sichtungsstufe"
            subtitle="Setzen der Sichtung startet die Behandlung (Zeitstempel automatisch)."
            testId="section-sichtung"
          >
            <SichtungGrid
              value={patient.sichtung || ''}
              onSelect={handleSichtung}
              disabled={busy}
            />
          </SectionCard>

          <SectionCard
            title="Behandelnde Ressource"
            subtitle="Zuordnung zeigt, wer die Behandlung begonnen hat."
            testId="section-behandlung-ressource"
          >
            <div className="max-w-sm space-y-2">
              <Label className="text-caption" htmlFor="pd-behandlung-ressource">
                Ressource
              </Label>
              <Select
                value={patient.behandlung_ressource_id || 'none'}
                onValueChange={handleTreatmentResourceChange}
              >
                <SelectTrigger
                  id="pd-behandlung-ressource"
                  data-testid="pd-behandlung-ressource"
                  className="bg-background"
                  disabled={busy || closed}
                >
                  <SelectValue placeholder="Ressource waehlen" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">(keine)</SelectItem>
                  {availableTreatmentResources.map((r) => (
                    <SelectItem key={r.id} value={r.id}>
                      {r.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {currentTreatmentResourceLabel && (
                <p className="text-caption text-muted-foreground">
                  Aktuell zugewiesen: {currentTreatmentResourceLabel}
                </p>
              )}
            </div>
          </SectionCard>

          <SectionCard
            title="Notiz"
            subtitle={
              notizSaved
                ? 'Automatisch gespeichert'
                : 'Aenderungen werden gespeichert …'
            }
            testId="section-notiz"
          >
            <Textarea
              value={notiz}
              onChange={(e) => setNotiz(e.target.value)}
              rows={4}
              maxLength={4000}
              placeholder="Beobachtungen, Anamnese, Massnahmen …"
              data-testid="pd-notiz"
              className="bg-background"
            />
          </SectionCard>

          <SectionCard title="Transport" testId="section-transport">
            {patient.transport_typ ? (
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Truck className="h-4 w-4 text-primary" />
                  <span>
                    <span className="text-caption text-muted-foreground mr-1">
                      Typ:
                    </span>
                    <span className="font-medium">
                      {TRANSPORT_TYP[patient.transport_typ].label}
                    </span>
                  </span>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setTransportOpen(true)}
                  disabled={busy || closed}
                  data-testid="pd-transport-change"
                >
                  Aendern
                </Button>
              </div>
            ) : (
              <div className="flex items-center justify-between gap-3">
                <div className="text-caption text-muted-foreground">
                  Noch kein Transport angefordert.
                </div>
                <Button
                  onClick={() => setTransportOpen(true)}
                  disabled={busy || !patient.sichtung || closed}
                  data-testid="pd-transport-request"
                >
                  <Truck className="h-4 w-4" />
                  Transport anfordern
                </Button>
              </div>
            )}
          </SectionCard>

          <SectionCard title="Bett-Zuweisung" testId="section-bett">
            {currentBett ? (
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 min-w-0">
                  <Bed className="h-4 w-4 text-primary shrink-0" />
                  <div className="min-w-0">
                    <div className="text-body font-medium truncate">
                      {currentBett.name}
                    </div>
                    <div className="text-caption text-muted-foreground flex items-center gap-1.5">
                      <span>{currentBett.typ}</span>
                      {currentBett.abschnitt_id &&
                        abschnittById.get(currentBett.abschnitt_id) && (
                          <>
                            <span>·</span>
                            <span
                              className={cn(
                                'inline-flex items-center gap-1 rounded px-1.5 py-0.5',
                                getFarbe(
                                  abschnittById.get(currentBett.abschnitt_id)
                                    .farbe,
                                ).soft,
                              )}
                            >
                              <span
                                className={cn(
                                  'h-1.5 w-1.5 rounded-full',
                                  getFarbe(
                                    abschnittById.get(currentBett.abschnitt_id)
                                      .farbe,
                                  ).dot,
                                )}
                              />
                              {abschnittById.get(currentBett.abschnitt_id).name}
                            </span>
                          </>
                        )}
                    </div>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setBettModalOpen(true)}
                    disabled={busy || closed || !can('bett.assign_patient')}
                    data-testid="pd-bett-change"
                  >
                    Aendern
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-status-red"
                    onClick={handleReleaseBett}
                    disabled={busy || closed || !can('bett.release')}
                    data-testid="pd-bett-release"
                  >
                    <UserMinus className="h-3.5 w-3.5" />
                    Freigeben
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-between gap-3">
                <div className="text-caption text-muted-foreground">
                  Kein Bett zugewiesen.
                </div>
                <Button
                  onClick={() => setBettModalOpen(true)}
                  disabled={busy || closed || !can('bett.assign_patient')}
                  data-testid="pd-bett-assign"
                >
                  <Bed className="h-4 w-4" />
                  Bett zuweisen
                </Button>
              </div>
            )}
          </SectionCard>

          <SectionCard
            title="Fallabschluss"
            subtitle="Verbleib wird automatisch gesetzt."
            testId="section-abschluss"
          >
            {patient.fallabschluss_typ ? (
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <FileCheck2 className="h-4 w-4 text-primary" />
                  <span>
                    <span className="text-caption text-muted-foreground mr-1">
                      Typ:
                    </span>
                    <span className="font-medium">
                      {FALLABSCHLUSS_TYP[patient.fallabschluss_typ].label}
                    </span>
                  </span>
                </div>
                <StatusBadge tone="green" variant="soft" size="sm">
                  Abgeschlossen
                </StatusBadge>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-caption text-muted-foreground">
                    {(patient.wiedereroeffnet_at || []).length > 0
                      ? `Wiedereroeffnet · aktuell offen (${(patient.wiedereroeffnet_at || []).length}× erneut aufgenommen)`
                      : 'Noch nicht abgeschlossen.'}
                  </div>
                  <Button
                    variant="outline"
                    onClick={() => setAbschlussOpen(true)}
                    disabled={busy}
                    data-testid="pd-abschluss-open"
                  >
                    <FileCheck2 className="h-4 w-4" />
                    Fall abschliessen
                  </Button>
                </div>
              </div>
            )}
            {/* Wiedereroeffnen-Option fuer abgeschlossene Patienten */}
            {(patient.status === 'uebergeben' ||
              patient.status === 'entlassen') && (
              <div className="mt-3 flex items-center justify-between gap-3 rounded-md border border-border bg-surface-sunken px-3 py-2">
                <div className="text-caption text-muted-foreground">
                  Patient kehrt zurueck? Wiedereroeffnung setzt den Fall auf "In
                  Behandlung" zurueck und protokolliert den Zeitstempel.
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={busy || !can('patient.reopen')}
                  onClick={() => setReopenOpen(true)}
                  data-testid="pd-reopen-btn"
                  title={
                    can('patient.reopen')
                      ? 'Fall wiedereroeffnen'
                      : 'Keine Berechtigung'
                  }
                >
                  <RotateCcw className="h-4 w-4" />
                  Wiedereroeffnen
                </Button>
              </div>
            )}
          </SectionCard>

          <SectionCard title="Verbleib" testId="section-verbleib">
            <div className="max-w-xs">
              <Label className="text-caption" htmlFor="pd-verbleib">
                Ziel / Verbleib
              </Label>
              <Select value={verbleib} onValueChange={handleVerbleibChange}>
                <SelectTrigger
                  id="pd-verbleib"
                  data-testid="pd-verbleib"
                  className="mt-1 bg-background"
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {VERBLEIB_OPTIONS.map((s) => (
                    <SelectItem key={s} value={s}>
                      {PATIENT_VERBLEIB[s]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </SectionCard>
        </div>

        {/* Rechte Spalte: Timeline + Aktionen */}
        <div className="space-y-4">
          <SectionCard title="Zeitverlauf" testId="section-timeline">
            <PatientTimeline patient={patient} />
          </SectionCard>

          <SectionCard title="Gefahrenbereich" testId="section-danger">
            <div className="flex items-center justify-between gap-3">
              <div className="text-caption text-muted-foreground">
                Patient aus Liste entfernen.
              </div>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setDeleteOpen(true)}
                data-testid="pd-delete"
              >
                <Trash2 className="h-3.5 w-3.5" />
                Loeschen
              </Button>
            </div>
          </SectionCard>
        </div>
      </div>

      <TransportChoiceDialog
        open={transportOpen}
        onOpenChange={setTransportOpen}
        onSelect={handleTransport}
      />
      <FallabschlussChoiceDialog
        open={abschlussOpen}
        onOpenChange={setAbschlussOpen}
        onSelect={handleAbschluss}
      />
      <ConfirmModal
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title={`Patient ${patient.kennung} loeschen?`}
        description="Der Eintrag wird unwiderruflich entfernt."
        confirmLabel="Loeschen"
        tone="destructive"
        onConfirm={handleDelete}
      />
      <ConfirmModal
        open={reopenOpen}
        onOpenChange={setReopenOpen}
        title={`Patient ${patient.kennung} wiedereroeffnen?`}
        description="Der Fall wird auf 'In Behandlung' gesetzt, Fallabschluss zurueckgesetzt und der Zeitstempel protokolliert. Diese Aktion ist fuer Patienten gedacht, die nach Entlassung/Uebergabe erneut versorgt werden muessen."
        confirmLabel="Wiedereroeffnen"
        onConfirm={handleReopen}
        testId="pd-reopen-confirm"
      />

      {/* Bett-Zuweisungs-Dialog */}
      {bettModalOpen && (
        <BettPickDialog
          open={bettModalOpen}
          onOpenChange={setBettModalOpen}
          betten={betten.filter(
            (b) =>
              b.status !== 'gesperrt' &&
              (b.status !== 'belegt' || b.id === currentBett?.id),
          )}
          abschnittById={abschnittById}
          currentBettId={currentBett?.id}
          onPick={handleAssignBett}
        />
      )}
    </div>
  );
}

// Kompaktes Bett-Auswahl-Dialog (lokal, da nur hier genutzt)
function BettPickDialog({
  open,
  onOpenChange,
  betten,
  abschnittById,
  currentBettId,
  onPick,
}) {
  return (
    <ConfirmModal
      open={open}
      onOpenChange={onOpenChange}
      title="Bett zuweisen"
      description={
        betten.length === 0
          ? 'Keine freien Betten verfuegbar.'
          : 'Waehle ein freies Bett. Belegte und gesperrte Betten sind ausgeblendet.'
      }
      confirmLabel="Abbrechen"
      onConfirm={() => onOpenChange(false)}
    >
      <ul
        className="max-h-[50vh] overflow-y-auto space-y-1.5"
        data-testid="bett-pick-list"
      >
        {betten.map((b) => {
          const a = b.abschnitt_id ? abschnittById.get(b.abschnitt_id) : null;
          const farbe = a ? getFarbe(a.farbe) : null;
          const isCurrent = b.id === currentBettId;
          return (
            <li key={b.id}>
              <button
                type="button"
                onClick={() => onPick(b.id)}
                className="flex w-full items-center gap-2 rounded-md bg-surface-raised px-3 py-2 text-left hover:border-primary/60 border border-transparent els-focus-ring"
                data-testid={`bett-pick-${b.id}`}
              >
                <Bed className="h-4 w-4 text-muted-foreground" />
                <div className="flex-1 min-w-0">
                  <div className="text-body font-medium">{b.name}</div>
                  <div className="text-caption text-muted-foreground flex items-center gap-1.5">
                    <span>{b.typ}</span>
                    {a && (
                      <span
                        className={cn(
                          'inline-flex items-center gap-1 rounded px-1 py-0.5',
                          farbe.soft,
                        )}
                      >
                        <span
                          className={cn('h-1 w-1 rounded-full', farbe.dot)}
                        />
                        {a.name}
                      </span>
                    )}
                  </div>
                </div>
                {isCurrent && (
                  <StatusBadge tone="info" variant="soft" size="sm">
                    AKTUELL
                  </StatusBadge>
                )}
              </button>
            </li>
          );
        })}
      </ul>
    </ConfirmModal>
  );
}
