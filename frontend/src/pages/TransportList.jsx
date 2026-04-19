import * as React from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
    KpiTile,
    StatusBadge,
    ConfirmModal
} from "@/components/primitives";
import { useTransports } from "@/context/TransportContext";
import { useIncidents } from "@/context/IncidentContext";
import { usePatients } from "@/context/PatientContext";
import { TransportCard } from "@/components/transports/TransportCard";
import { ResourceBar } from "@/components/transports/ResourceBar";
import {
    ResourceAssignDialog,
    NewTransportDialog
} from "@/components/transports/TransportDialogs";
import {
    Truck,
    Stethoscope,
    ArrowLeft,
    RefreshCw,
    Plus,
    Inbox
} from "lucide-react";
import { TRANSPORT_STATUS, STATUS_BUCKETS } from "@/lib/transport-meta";
import { cn } from "@/lib/utils";

function ColumnEmpty({ label }) {
    return (
        <div className="flex items-center justify-center rounded-md border border-dashed border-border py-4 text-caption text-muted-foreground">
            {label}
        </div>
    );
}

function Bucket({ title, items, tone, onDragOverBucket, onDropBucket, ...handlers }) {
    const [over, setOver] = React.useState(false);
    const count = items.length;
    return (
        <section
            onDragOver={(e) => {
                if (onDropBucket) {
                    e.preventDefault();
                    e.dataTransfer.dropEffect = "move";
                    setOver(true);
                }
            }}
            onDragLeave={() => setOver(false)}
            onDrop={(e) => {
                setOver(false);
                if (onDropBucket) {
                    e.preventDefault();
                    const tid = e.dataTransfer.getData("text/transport-id");
                    if (tid) onDropBucket(tid);
                }
            }}
            data-testid={`bucket-${title.toLowerCase()}`}
            className={cn(
                "rounded-md border border-border bg-surface-sunken/60 p-2",
                over && "ring-2 ring-primary/60 bg-primary/5"
            )}
        >
            <header className="mb-2 flex items-center justify-between px-1">
                <div className="flex items-center gap-2">
                    <StatusBadge tone={tone} variant="soft" size="sm">
                        {title}
                    </StatusBadge>
                    <span className="text-caption font-mono text-muted-foreground">
                        {count}
                    </span>
                </div>
            </header>
            {count === 0 ? (
                <ColumnEmpty label="keine" />
            ) : (
                <div className="flex flex-col gap-2">
                    {items.map((t) => (
                        <TransportCard key={t.id} transport={t} {...handlers} />
                    ))}
                </div>
            )}
        </section>
    );
}

function TypColumn({ typ, title, icon: Icon, transports, ...handlers }) {
    const byStatus = React.useMemo(() => {
        const m = Object.fromEntries(STATUS_BUCKETS.map((s) => [s, []]));
        for (const t of transports) {
            (m[t.status] || m.offen).push(t);
        }
        return m;
    }, [transports]);

    const offenCount = byStatus.offen.length;
    const fehlendeRessource = transports.filter(
        (t) => t.status === "offen" && !t.ressource
    ).length;

    return (
        <div
            className="els-surface flex flex-col gap-3 p-3"
            data-testid={`transport-col-${typ}`}
        >
            <header className="flex items-center justify-between gap-2 border-b border-border pb-2">
                <div className="flex items-center gap-2">
                    <Icon className="h-4 w-4 text-primary" />
                    <h2 className="text-heading">{title}</h2>
                    <span className="font-mono text-caption text-muted-foreground">
                        {transports.length}
                    </span>
                </div>
                {fehlendeRessource > 0 && (
                    <StatusBadge tone="yellow" size="sm" variant="soft">
                        {fehlendeRessource} ohne Ressource
                    </StatusBadge>
                )}
            </header>

            <Bucket
                title="Offen"
                tone="yellow"
                items={byStatus.offen}
                onDropBucket={(tid) => handlers.onBucketDrop?.(tid, "offen")}
                {...handlers}
            />
            <Bucket
                title="Zugewiesen"
                tone="info"
                items={byStatus.zugewiesen}
                {...handlers}
            />
            <Bucket
                title="Unterwegs"
                tone="green"
                items={byStatus.unterwegs}
                {...handlers}
            />
            <Bucket
                title="Abgeschlossen"
                tone="gray"
                items={byStatus.abgeschlossen}
                {...handlers}
            />
        </div>
    );
}

export default function TransportList() {
    const navigate = useNavigate();
    const { activeIncident } = useIncidents();
    const {
        transports,
        loading,
        error,
        refresh,
        create,
        update,
        remove,
        kpis
    } = useTransports();
    const { refresh: refreshPatients } = usePatients();

    const [assignFor, setAssignFor] = React.useState(null);
    const [newOpen, setNewOpen] = React.useState(false);
    const [deleteCandidate, setDeleteCandidate] = React.useState(null);

    const intern = transports.filter((t) => t.typ === "intern");
    const extern = transports.filter((t) => t.typ === "extern");

    const handleAssign = React.useCallback(
        async (tid, ressource) => {
            try {
                await update(tid, { ressource });
            } catch (e) {
                console.error("Assign fehlgeschlagen", e);
            }
        },
        [update]
    );

    const handleUnassign = React.useCallback(
        async (t) => {
            try {
                await update(t.id, { ressource: "", status: "offen" });
            } catch (e) {
                console.error("Unassign fehlgeschlagen", e);
            }
        },
        [update]
    );

    const handleStart = React.useCallback(
        async (t) => {
            try {
                await update(t.id, { status: "unterwegs" });
            } catch (e) {
                console.error("Start fehlgeschlagen", e);
            }
        },
        [update]
    );

    const handleComplete = React.useCallback(
        async (t) => {
            try {
                await update(t.id, { status: "abgeschlossen" });
                // Patient-Status koennte durch Backend-Logik indirekt betroffen sein
                refreshPatients();
            } catch (e) {
                console.error("Complete fehlgeschlagen", e);
            }
        },
        [update, refreshPatients]
    );

    const handleOpenPatient = React.useCallback(
        (t) => {
            if (t.patient_id) navigate(`/patienten/${t.patient_id}`);
        },
        [navigate]
    );

    const handleBucketDrop = React.useCallback(
        async (tid, bucket) => {
            if (bucket === "offen") {
                await update(tid, { ressource: "", status: "offen" });
            }
        },
        [update]
    );

    if (!activeIncident) {
        return (
            <div className="mx-auto max-w-xl p-6">
                <div className="els-surface p-6 text-center" data-testid="transport-no-incident">
                    <h2 className="text-display">Kein Incident aktiv</h2>
                    <p className="mt-2 text-muted-foreground">
                        Waehle zunaechst einen Incident.
                    </p>
                    <Button className="mt-4" onClick={() => navigate("/")}>
                        <ArrowLeft className="h-4 w-4" />
                        Incident-Uebersicht
                    </Button>
                </div>
            </div>
        );
    }

    const sharedCardHandlers = {
        onAssign: (t) => setAssignFor(t),
        onStart: handleStart,
        onComplete: handleComplete,
        onUnassign: handleUnassign,
        onDelete: (t) => setDeleteCandidate(t),
        onOpenPatient: handleOpenPatient,
        onBucketDrop: handleBucketDrop
    };

    return (
        <div className="flex h-full flex-col">
            <div className="flex-1 overflow-y-auto px-6 py-6">
                <div className="mx-auto w-full max-w-[1600px]">
                    {/* Kopfzeile */}
                    <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
                        <div>
                            <div className="text-caption uppercase tracking-wider text-muted-foreground">
                                Schritt 05 · Transporte
                            </div>
                            <h1
                                className="mt-1 text-display"
                                data-testid="transport-list-title"
                            >
                                Transportuebersicht
                            </h1>
                            <p className="text-caption text-muted-foreground">
                                Aktiver Incident:{" "}
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
                                data-testid="transport-refresh"
                            >
                                <RefreshCw className="h-4 w-4" />
                                Aktualisieren
                            </Button>
                            <Button
                                onClick={() => setNewOpen(true)}
                                data-testid="transport-new"
                            >
                                <Plus className="h-4 w-4" />
                                Neuer Transport
                            </Button>
                        </div>
                    </div>

                    {/* KPI-Leiste */}
                    <div className="mb-4 grid grid-cols-2 gap-2 md:grid-cols-6">
                        <KpiTile
                            label="Gesamt"
                            value={kpis.total}
                            tone="default"
                            testId="kpi-tr-total"
                        />
                        <KpiTile
                            label="Offen"
                            value={kpis.offen}
                            tone="yellow"
                            testId="kpi-tr-offen"
                        />
                        <KpiTile
                            label="Zugewiesen"
                            value={kpis.zugewiesen}
                            tone="default"
                            testId="kpi-tr-zugewiesen"
                        />
                        <KpiTile
                            label="Unterwegs"
                            value={kpis.unterwegs}
                            tone="green"
                            testId="kpi-tr-unterwegs"
                        />
                        <KpiTile
                            label="Intern"
                            value={kpis.intern}
                            tone="gray"
                            testId="kpi-tr-intern"
                        />
                        <KpiTile
                            label="Extern"
                            value={kpis.extern}
                            tone="gray"
                            testId="kpi-tr-extern"
                        />
                    </div>

                    {error && (
                        <div className="mb-3 rounded-md border border-status-red/40 bg-status-red/10 px-3 py-2 text-caption text-status-red">
                            {error}
                        </div>
                    )}

                    {loading && transports.length === 0 ? (
                        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                            {Array.from({ length: 2 }).map((_, i) => (
                                <div
                                    key={i}
                                    className="els-surface h-64 animate-pulse bg-surface-raised/60"
                                />
                            ))}
                        </div>
                    ) : transports.length === 0 ? (
                        <div
                            className="els-surface flex flex-col items-center gap-3 py-14 text-center"
                            data-testid="transport-empty"
                        >
                            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
                                <Inbox className="h-6 w-6" />
                            </div>
                            <div>
                                <h3 className="text-heading">
                                    Noch keine Transporte
                                </h3>
                                <p className="mt-1 max-w-md text-caption text-muted-foreground">
                                    Transporte entstehen automatisch, wenn ein
                                    Patient eine Transportanforderung erhaelt.
                                </p>
                            </div>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setNewOpen(true)}
                                data-testid="transport-empty-new"
                            >
                                <Plus className="h-4 w-4" />
                                Manuell anlegen
                            </Button>
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                            <TypColumn
                                typ="intern"
                                title="Intern (UHS)"
                                icon={Stethoscope}
                                transports={intern}
                                {...sharedCardHandlers}
                            />
                            <TypColumn
                                typ="extern"
                                title="Extern (RD / KH)"
                                icon={Truck}
                                transports={extern}
                                {...sharedCardHandlers}
                            />
                        </div>
                    )}
                </div>
            </div>

            <ResourceBar
                transports={transports}
                onAssign={handleAssign}
                onNewTransport={() => setNewOpen(true)}
            />

            <ResourceAssignDialog
                open={assignFor !== null}
                onOpenChange={(v) => !v && setAssignFor(null)}
                transport={assignFor}
                transports={transports}
                onAssign={(name) => {
                    if (assignFor) handleAssign(assignFor.id, name);
                }}
            />

            <NewTransportDialog
                open={newOpen}
                onOpenChange={setNewOpen}
                onCreate={async (payload) => {
                    await create(payload);
                }}
            />

            <ConfirmModal
                open={deleteCandidate !== null}
                onOpenChange={(v) => !v && setDeleteCandidate(null)}
                title="Transport loeschen?"
                description={
                    deleteCandidate
                        ? `${deleteCandidate.patient_kennung || "Transport"} wird entfernt.`
                        : ""
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
