import * as React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  StatusBadge,
  SichtungBadge,
  FilterChip,
  KpiTile,
  DataTable,
  ConfirmModal,
} from '@/components/primitives';
import { usePatients, isPatientClosed } from '@/context/PatientContext';
import { useIncidents } from '@/context/IncidentContext';
import { useCommandPalette } from '@/components/command/CommandPalette';
import { QuickEntryBar } from '@/components/patients/QuickEntryBar';
import { PatientDialog } from '@/components/patients/PatientDialog';
import {
  Search,
  RefreshCw,
  Plus,
  Trash2,
  ChevronRight,
  ArrowLeft,
  Inbox,
  Activity,
  Eye,
  EyeOff,
} from 'lucide-react';
import {
  SICHTUNG,
  PATIENT_STATUS,
  PATIENT_VERBLEIB,
  STATUS_OPTIONS,
} from '@/lib/patient-meta';
import { formatDuration } from '@/lib/time';

function EmptyState({ hasFilter, onQuickS2 }) {
  return (
    <div
      className="els-surface flex flex-col items-center gap-3 py-14 px-6 text-center"
      data-testid="patient-list-empty"
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
        <Inbox className="h-6 w-6" />
      </div>
      <div>
        <h3 className="text-heading">
          {hasFilter ? 'Keine Treffer' : 'Noch keine Patienten erfasst'}
        </h3>
        <p className="mt-1 max-w-md text-caption text-muted-foreground">
          {hasFilter
            ? 'Passe Filter oder Suche an, um weitere Patienten zu sehen.'
            : 'Nutze die Schnellerfassung unten (Tasten 1-4) fuer sofortige Anlage einer Sichtung.'}
        </p>
      </div>
      {!hasFilter && (
        <Button
          size="sm"
          variant="outline"
          onClick={onQuickS2}
          data-testid="empty-quick-s2"
        >
          Ersten S2-Patienten anlegen
        </Button>
      )}
    </div>
  );
}

function DauerSeitSichtung({ patient }) {
  const [now, setNow] = React.useState(() => Date.now());
  React.useEffect(() => {
    if (!patient.sichtung_at) return undefined;
    if (patient.status === 'uebergeben' || patient.status === 'entlassen')
      return undefined;
    const id = setInterval(() => setNow(Date.now()), 30 * 1000);
    return () => clearInterval(id);
  }, [patient.sichtung_at, patient.status]);

  if (!patient.sichtung_at)
    return <span className="text-muted-foreground">–</span>;
  const end = patient.fallabschluss_at
    ? new Date(patient.fallabschluss_at).getTime()
    : now;
  return (
    <span className="font-mono tabular-nums">
      {formatDuration(end - new Date(patient.sichtung_at).getTime())}
    </span>
  );
}

export default function PatientList() {
  const navigate = useNavigate();
  const { activeIncident } = useIncidents();
  const { patients, loading, error, refresh, create, update, remove, kpis } =
    usePatients();
  const { registerCommand } = useCommandPalette();

  const [sichtungFilter, setSichtungFilter] = React.useState(() => ({
    S1: true,
    S2: true,
    S3: true,
    S0: true,
  }));
  const [statusFilter, setStatusFilter] = React.useState('alle');
  const [query, setQuery] = React.useState('');
  const [dialogOpen, setDialogOpen] = React.useState(false);
  const [editPatient, setEditPatient] = React.useState(null);
  const [deleteCandidate, setDeleteCandidate] = React.useState(null);
  // Abgeschlossene Patienten per Default ausblenden
  const [showClosed, setShowClosed] = React.useState(false);
  // KPI-Modus: "offen" (Default) oder "alle" – Umschaltung am oberen Rand
  const [kpiMode, setKpiMode] = React.useState('offen');

  // Liste filtern
  const filtered = React.useMemo(() => {
    const q = query.trim().toLowerCase();
    return patients.filter((p) => {
      // Abgeschlossene standardmaessig ausblenden
      if (!showClosed && isPatientClosed(p)) return false;
      // Sichtung
      if (p.sichtung) {
        if (!sichtungFilter[p.sichtung]) return false;
      } else if (!Object.values(sichtungFilter).some(Boolean)) {
        // alle abgewaehlt -> auch "unsichtiert" ausblenden
        return false;
      }
      // Status
      if (statusFilter !== 'alle' && p.status !== statusFilter) return false;
      // Query
      if (q) {
        const blob =
          `${p.kennung} ${p.notiz || ''} ${p.verbleib || ''} ${p.status || ''} ${p.behandlung_ressource_name || ''}`.toLowerCase();
        if (!blob.includes(q)) return false;
      }
      return true;
    });
  }, [patients, sichtungFilter, statusFilter, query, showClosed]);

  const toggleSichtung = (k) =>
    setSichtungFilter((s) => ({ ...s, [k]: !s[k] }));

  // Commands fuer Patienten registrieren
  React.useEffect(() => {
    const unregs = [];
    for (const p of patients) {
      unregs.push(
        registerCommand({
          id: `patient-jump-${p.id}`,
          label: `${p.kennung}${p.sichtung ? ` · ${p.sichtung}` : ''} · ${
            PATIENT_STATUS[p.status]?.label || p.status
          }`,
          group: 'Patienten',
          keywords: [
            p.kennung,
            p.sichtung || '',
            p.notiz || '',
            p.verbleib || '',
          ],
          run: () => navigate(`/patienten/${p.id}`),
        }),
      );
    }
    return () => unregs.forEach((u) => u && u());
  }, [patients, registerCommand, navigate]);

  // Kein aktiver Incident
  if (!activeIncident) {
    return (
      <div className="mx-auto max-w-xl p-6">
        <div
          className="els-surface p-6 text-center"
          data-testid="patients-no-incident"
        >
          <h2 className="text-display">Kein Incident aktiv</h2>
          <p className="mt-2 text-muted-foreground">
            Waehle zunaechst einen Incident, um Patienten zu erfassen.
          </p>
          <Button
            className="mt-4"
            onClick={() => navigate('/')}
            data-testid="patients-goto-incidents"
          >
            <ArrowLeft className="h-4 w-4" />
            Incident-Uebersicht
          </Button>
        </div>
      </div>
    );
  }

  const handleQuickCreate = async ({ sichtung }) => {
    await create({ sichtung });
  };

  const openNew = () => {
    setEditPatient(null);
    setDialogOpen(true);
  };
  const openEdit = (p) => {
    setEditPatient(p);
    setDialogOpen(true);
  };

  const columns = [
    {
      key: 'kennung',
      label: 'Kennung',
      width: '10%',
      render: (p) => <span className="font-mono font-medium">{p.kennung}</span>,
    },
    {
      key: 'sichtung',
      label: 'Sichtung',
      width: '10%',
      render: (p) =>
        p.sichtung ? (
          <SichtungBadge level={p.sichtung} />
        ) : (
          <StatusBadge tone="neutral" size="sm" variant="outline">
            ausstehend
          </StatusBadge>
        ),
    },
    {
      key: 'status',
      label: 'Status',
      width: '18%',
      render: (p) => {
        const meta = PATIENT_STATUS[p.status] || {
          label: p.status,
          tone: 'neutral',
        };
        return (
          <StatusBadge
            tone={meta.tone}
            variant="soft"
            size="sm"
            dot={p.status === 'in_behandlung' || p.status === 'wartend'}
          >
            {meta.label}
          </StatusBadge>
        );
      },
    },
    {
      key: 'verbleib',
      label: 'Verbleib',
      width: '14%',
      render: (p) => (
        <span
          className={p.verbleib === 'unbekannt' ? 'text-muted-foreground' : ''}
        >
          {PATIENT_VERBLEIB[p.verbleib] || p.verbleib}
        </span>
      ),
    },
    {
      key: 'behandlung_ressource',
      label: 'Behandler',
      width: '14%',
      render: (p) =>
        p.behandlung_ressource_name ? (
          <span className="text-body">{p.behandlung_ressource_name}</span>
        ) : (
          <span className="text-muted-foreground/60">–</span>
        ),
    },
    {
      key: 'dauer',
      label: 'Dauer',
      width: '10%',
      align: 'right',
      render: (p) => <DauerSeitSichtung patient={p} />,
    },
    {
      key: 'notiz',
      label: 'Notiz',
      render: (p) =>
        p.notiz ? (
          <span className="text-muted-foreground line-clamp-1" title={p.notiz}>
            {p.notiz}
          </span>
        ) : (
          <span className="text-muted-foreground/60">–</span>
        ),
    },
    {
      key: 'actions',
      label: '',
      width: '6%',
      align: 'right',
      render: (p) => (
        <div className="flex items-center justify-end gap-1">
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="h-7 w-7"
            onClick={(e) => {
              e.stopPropagation();
              setDeleteCandidate(p);
            }}
            data-testid={`patient-delete-${p.id}`}
            title="Loeschen"
          >
            <Trash2 className="h-3.5 w-3.5 text-muted-foreground hover:text-destructive" />
          </Button>
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        </div>
      ),
    },
  ];

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto w-full max-w-[1600px]">
          {/* Kopfzeile */}
          <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 text-caption uppercase tracking-wider text-muted-foreground">
                <Activity className="h-3 w-3" />
                Schritt 03 · Patienten
              </div>
              <h1
                className="mt-1 text-display"
                data-testid="patient-list-title"
              >
                Patientenliste
              </h1>
              <p className="text-caption text-muted-foreground">
                Aktiver Incident:{' '}
                <span className="font-medium text-foreground">
                  {activeIncident.name}
                </span>
                {activeIncident.demo && (
                  <StatusBadge
                    tone="yellow"
                    variant="solid"
                    size="sm"
                    className="ml-2"
                  >
                    DEMO
                  </StatusBadge>
                )}
              </p>
            </div>
            <div className="flex gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={refresh}
                data-testid="patient-refresh"
              >
                <RefreshCw className="h-4 w-4" />
                Aktualisieren
              </Button>
              <Button onClick={openNew} data-testid="patient-new">
                <Plus className="h-4 w-4" />
                Neuer Patient
              </Button>
            </div>
          </div>

          {/* KPI-Leiste mit Umschalter Offene / Gesamt */}
          {(() => {
            const kpiSet = kpiMode === 'alle' ? kpis.alle : kpis.offen;
            const totalLabel = kpiMode === 'alle' ? 'Gesamt' : 'Offene';
            return (
              <div className="mb-4 space-y-2" data-testid="kpi-section">
                <div
                  className="inline-flex rounded-md border border-border bg-surface-sunken p-0.5"
                  role="tablist"
                  aria-label="KPI-Umschalter"
                >
                  <button
                    type="button"
                    role="tab"
                    aria-selected={kpiMode === 'offen'}
                    onClick={() => setKpiMode('offen')}
                    data-testid="kpi-mode-offen"
                    className={
                      'px-3 py-1 text-caption rounded transition-colors ' +
                      (kpiMode === 'offen'
                        ? 'bg-primary/15 text-primary'
                        : 'text-muted-foreground hover:text-foreground')
                    }
                  >
                    Offene ({kpis.offen.total})
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={kpiMode === 'alle'}
                    onClick={() => setKpiMode('alle')}
                    data-testid="kpi-mode-alle"
                    className={
                      'px-3 py-1 text-caption rounded transition-colors ' +
                      (kpiMode === 'alle'
                        ? 'bg-primary/15 text-primary'
                        : 'text-muted-foreground hover:text-foreground')
                    }
                  >
                    Gesamt ({kpis.alle.total})
                  </button>
                </div>
                <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-8">
                  <KpiTile
                    label={totalLabel}
                    value={kpiSet.total}
                    tone="default"
                    testId="kpi-total"
                    hint={
                      kpiMode === 'alle'
                        ? `${kpiSet.abgeschlossen} abgeschlossen`
                        : null
                    }
                  />
                  <KpiTile
                    label="S1"
                    value={kpiSet.S1}
                    tone="red"
                    testId="kpi-s1"
                  />
                  <KpiTile
                    label="S2"
                    value={kpiSet.S2}
                    tone="yellow"
                    testId="kpi-s2"
                  />
                  <KpiTile
                    label="S3"
                    value={kpiSet.S3}
                    tone="green"
                    testId="kpi-s3"
                  />
                  <KpiTile
                    label="S0"
                    value={kpiSet.S0}
                    tone="gray"
                    testId="kpi-s0"
                  />
                  <KpiTile
                    label="Wartend"
                    value={kpiSet.wartend}
                    tone="yellow"
                    testId="kpi-wartend"
                  />
                  <KpiTile
                    label="In Beh."
                    value={kpiSet.behandlung}
                    tone="default"
                    testId="kpi-beh"
                  />
                  <KpiTile
                    label="Transport"
                    value={kpiSet.transport}
                    tone="green"
                    testId="kpi-transport"
                  />
                </div>
              </div>
            );
          })()}

          {/* Filter- und Suchleiste */}
          <div className="mb-3 flex flex-wrap items-center gap-3 rounded-md border border-border bg-surface-sunken px-3 py-2.5">
            <div className="flex flex-wrap gap-1.5">
              <span className="text-caption text-muted-foreground mr-1">
                Sichtung:
              </span>
              {SICHTUNG.map((s) => (
                <FilterChip
                  key={s.key}
                  tone={s.tone}
                  active={sichtungFilter[s.key]}
                  onToggle={() => toggleSichtung(s.key)}
                  count={kpis[s.key]}
                  data-testid={`filter-sichtung-${s.key}`}
                >
                  {s.label}
                </FilterChip>
              ))}
            </div>
            <span className="mx-1 h-4 w-px bg-border" />
            <div className="flex flex-wrap gap-1.5">
              <span className="text-caption text-muted-foreground mr-1">
                Status:
              </span>
              <FilterChip
                active={statusFilter === 'alle'}
                onToggle={() => setStatusFilter('alle')}
                data-testid="filter-status-alle"
              >
                Alle
              </FilterChip>
              {STATUS_OPTIONS.map((s) => {
                const meta = PATIENT_STATUS[s];
                return (
                  <FilterChip
                    key={s}
                    tone={meta.tone === 'info' ? 'neutral' : meta.tone}
                    active={statusFilter === s}
                    onToggle={() => setStatusFilter(s)}
                    data-testid={`filter-status-${s}`}
                  >
                    {meta.label}
                  </FilterChip>
                );
              })}
            </div>
            <div className="ml-auto flex items-center gap-2">
              <FilterChip
                active={showClosed}
                tone={showClosed ? 'info' : 'neutral'}
                onToggle={() => setShowClosed((v) => !v)}
                count={kpis.alle.abgeschlossen}
                data-testid="filter-show-closed"
              >
                {showClosed ? (
                  <>
                    <Eye className="h-3 w-3 mr-1" />
                    Abgeschlossene sichtbar
                  </>
                ) : (
                  <>
                    <EyeOff className="h-3 w-3 mr-1" />
                    Abgeschlossene einblenden
                  </>
                )}
              </FilterChip>
              <div className="relative">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input
                  type="search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Kennung, Notiz, Verbleib…"
                  className="h-8 w-64 bg-background pl-8"
                  data-testid="patient-search"
                />
              </div>
            </div>
          </div>

          {error && (
            <div className="mb-3 rounded-md border border-status-red/40 bg-status-red/10 px-3 py-2 text-caption text-status-red">
              {error}
            </div>
          )}

          {loading && patients.length === 0 ? (
            <div className="els-surface h-40 animate-pulse bg-surface-raised/60" />
          ) : filtered.length === 0 ? (
            <EmptyState
              hasFilter={
                query !== '' ||
                statusFilter !== 'alle' ||
                !Object.values(sichtungFilter).every(Boolean) ||
                !showClosed
              }
              onQuickS2={() => handleQuickCreate({ sichtung: 'S2' })}
            />
          ) : (
            <DataTable
              columns={columns}
              rows={filtered}
              rowTestId={(p) => `patient-row-${p.id}`}
              onRowClick={(p) => navigate(`/patienten/${p.id}`)}
              dense
              testId="patient-table"
            />
          )}
        </div>
      </div>

      {/* Schnellerfassung sticky bottom */}
      <QuickEntryBar onQuickCreate={handleQuickCreate} onOpenDialog={openNew} />

      <PatientDialog
        open={dialogOpen}
        onOpenChange={(v) => {
          setDialogOpen(v);
          if (!v) setEditPatient(null);
        }}
        initial={editPatient}
        onSubmit={async (payload) => {
          if (editPatient) {
            await update(editPatient.id, payload);
          } else {
            await create(payload);
          }
        }}
      />

      <ConfirmModal
        open={deleteCandidate !== null}
        onOpenChange={(v) => !v && setDeleteCandidate(null)}
        title="Patienten loeschen?"
        description={
          deleteCandidate
            ? `Kennung ${deleteCandidate.kennung} wird entfernt. Dies ist nicht rueckgaengig zu machen.`
            : ''
        }
        confirmLabel="Loeschen"
        tone="destructive"
        onConfirm={() => {
          if (deleteCandidate) remove(deleteCandidate.id);
          setDeleteCandidate(null);
        }}
      />
    </div>
  );
}
