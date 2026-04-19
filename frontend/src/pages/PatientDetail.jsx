import * as React from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue
} from "@/components/ui/select";
import {
    StatusBadge,
    SichtungBadge,
    KpiTile,
    SectionCard,
    ConfirmModal
} from "@/components/primitives";
import { PatientTimeline } from "@/components/patients/PatientTimeline";
import {
    TransportChoiceDialog,
    FallabschlussChoiceDialog
} from "@/components/patients/ChoiceDialogs";
import { usePatients } from "@/context/PatientContext";
import { useIncidents } from "@/context/IncidentContext";
import {
    ArrowLeft,
    ArrowRight,
    Trash2,
    AlertTriangle,
    CheckCircle2,
    Loader2,
    Truck,
    FileCheck2
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatDuration } from "@/lib/time";
import {
    SICHTUNG,
    PATIENT_STATUS,
    PATIENT_VERBLEIB,
    TRANSPORT_TYP,
    FALLABSCHLUSS_TYP,
    VERBLEIB_OPTIONS,
    nextProgression
} from "@/lib/patient-meta";
import { getPatient as apiGetPatient } from "@/lib/api";

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
                            "flex h-16 flex-col items-center justify-center rounded-md border font-semibold transition-colors disabled:opacity-60",
                            active && s.tone === "red" && "bg-status-red text-status-red-fg border-status-red",
                            active && s.tone === "yellow" && "bg-status-yellow text-status-yellow-fg border-status-yellow",
                            active && s.tone === "green" && "bg-status-green text-status-green-fg border-status-green",
                            active && s.tone === "gray" && "bg-status-gray text-status-gray-fg border-status-gray",
                            !active && "border-border text-foreground hover:bg-surface-raised"
                        )}
                    >
                        <span className="font-mono text-display leading-none">
                            {s.key}
                        </span>
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
            patient.status === "uebergeben" || patient.status === "entlassen";
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
                value={seitSichtung != null ? formatDuration(seitSichtung) : "–"}
                tone="default"
                testId="kpi-seit-sichtung"
            />
            <KpiTile
                label="Behandlungsdauer"
                value={
                    behandlungsdauer != null ? formatDuration(behandlungsdauer) : "–"
                }
                tone={behandlungsdauer != null ? "green" : "gray"}
                testId="kpi-behandlung"
            />
            <KpiTile
                label="Seit Transport-Anforderung"
                value={
                    transportdauer != null ? formatDuration(transportdauer) : "–"
                }
                tone={transportdauer != null ? "yellow" : "gray"}
                testId="kpi-transport"
            />
        </div>
    );
}

export default function PatientDetail() {
    const { patientId } = useParams();
    const navigate = useNavigate();
    const { activeIncident, setActive } = useIncidents();
    const { patients, update, remove, refresh } = usePatients();

    const [patient, setPatient] = React.useState(() =>
        patients.find((p) => p.id === patientId) || null
    );
    const [loading, setLoading] = React.useState(!patient);
    const [notiz, setNotiz] = React.useState(patient?.notiz || "");
    const [verbleib, setVerbleib] = React.useState(patient?.verbleib || "unbekannt");
    const [transportOpen, setTransportOpen] = React.useState(false);
    const [abschlussOpen, setAbschlussOpen] = React.useState(false);
    const [deleteOpen, setDeleteOpen] = React.useState(false);
    const [busy, setBusy] = React.useState(false);
    const [notizSaved, setNotizSaved] = React.useState(true);
    const [error, setError] = React.useState(null);

    // Sync aus Liste (z.B. nach refresh)
    React.useEffect(() => {
        const fromList = patients.find((p) => p.id === patientId);
        if (fromList) {
            setPatient(fromList);
            setNotiz((n) => (n === (fromList.notiz || "") ? n : fromList.notiz || ""));
            setVerbleib(fromList.verbleib || "unbekannt");
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
                setNotiz(p.notiz || "");
                setVerbleib(p.verbleib || "unbekannt");
                // Stelle sicher, dass Incident aktiv ist
                if (p.incident_id && activeIncident?.id !== p.incident_id) {
                    setActive(p.incident_id);
                }
            } catch (e) {
                if (!cancelled) setError("Patient nicht gefunden.");
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
            if ((patient.notiz || "") === notiz) return;
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
        800
    );

    const applyPatch = React.useCallback(
        async (patch, { silent = false } = {}) => {
            if (!patient) return;
            setBusy(true);
            setError(null);
            try {
                const updated = await update(patient.id, patch);
                setPatient(updated);
                return updated;
            } catch (e) {
                if (!silent)
                    setError(
                        e?.response?.data?.detail ||
                            e?.message ||
                            "Aktualisierung fehlgeschlagen"
                    );
                throw e;
            } finally {
                setBusy(false);
            }
        },
        [patient, update]
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

    const next = patient ? nextProgression(patient) : null;

    const handleNext = async () => {
        if (!next) return;
        if (next.type === "require-sichtung") {
            // Fokussiere die Sichtungs-Grid-Buttons
            document.querySelector('[data-testid="pd-sichtung-S1"]')?.focus();
            return;
        }
        if (next.type === "set-status") {
            await applyPatch(next.payload);
            return;
        }
        if (next.type === "ask-transport") {
            setTransportOpen(true);
            return;
        }
        if (next.type === "ask-fallabschluss") {
            setAbschlussOpen(true);
        }
    };

    const handleDelete = async () => {
        if (!patient) return;
        await remove(patient.id);
        navigate("/patienten");
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
                <div className="els-surface p-6 text-center" data-testid="patient-detail-error">
                    <AlertTriangle className="mx-auto h-8 w-8 text-status-red" />
                    <h2 className="mt-3 text-display">Patient nicht gefunden</h2>
                    <p className="mt-1 text-muted-foreground">{error}</p>
                    <Button
                        className="mt-4"
                        onClick={() => navigate("/patienten")}
                    >
                        <ArrowLeft className="h-4 w-4" />
                        Zurueck zur Liste
                    </Button>
                </div>
            </div>
        );
    }

    if (!patient) return null;

    const statusMeta =
        PATIENT_STATUS[patient.status] || { label: patient.status, tone: "neutral" };
    const closed =
        patient.status === "uebergeben" || patient.status === "entlassen";

    return (
        <div className="mx-auto w-full max-w-[1400px] px-6 py-6">
            {/* Kopfzeile */}
            <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                <div className="flex items-start gap-4">
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => navigate("/patienten")}
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
                            value={patient.sichtung || ""}
                            onSelect={handleSichtung}
                            disabled={busy}
                        />
                    </SectionCard>

                    <SectionCard
                        title="Notiz"
                        subtitle={
                            notizSaved
                                ? "Automatisch gespeichert"
                                : "Aenderungen werden gespeichert …"
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
                                            {
                                                FALLABSCHLUSS_TYP[patient.fallabschluss_typ]
                                                    .label
                                            }
                                        </span>
                                    </span>
                                </div>
                                <StatusBadge tone="green" variant="soft" size="sm">
                                    Abgeschlossen
                                </StatusBadge>
                            </div>
                        ) : (
                            <div className="flex items-center justify-between gap-3">
                                <div className="text-caption text-muted-foreground">
                                    Noch nicht abgeschlossen.
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
        </div>
    );
}
