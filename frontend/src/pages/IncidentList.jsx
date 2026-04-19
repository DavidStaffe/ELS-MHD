import * as React from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    FilterChip,
    StatusBadge,
    ConfirmModal
} from "@/components/primitives";
import { IncidentCard } from "@/components/incidents/IncidentCard";
import { NewIncidentDialog } from "@/components/incidents/NewIncidentDialog";
import { useIncidents } from "@/context/IncidentContext";
import { useCommandPalette } from "@/components/command/CommandPalette";
import {
    Plus,
    PlayCircle,
    Search,
    RefreshCw,
    Command as CommandIcon,
    ArrowRight,
    Inbox
} from "lucide-react";

const FILTERS = [
    { key: "alle", label: "Alle", match: () => true },
    {
        key: "operativ",
        label: "Operativ",
        match: (i) => i.status === "operativ"
    },
    { key: "geplant", label: "Geplant", match: (i) => i.status === "geplant" },
    {
        key: "abgeschlossen",
        label: "Abgeschlossen",
        match: (i) => i.status === "abgeschlossen"
    },
    { key: "demo", label: "Demo", match: (i) => i.demo === true, tone: "yellow" }
];

function IncidentListSkeleton() {
    return (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
                <div
                    key={i}
                    className="els-surface h-56 animate-pulse bg-surface-raised/60"
                    aria-hidden
                />
            ))}
        </div>
    );
}

function EmptyState({ onNew, onDemo, hasFilter }) {
    return (
        <div
            className="els-surface flex flex-col items-center gap-4 py-16 px-6 text-center"
            data-testid="incident-list-empty"
        >
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 text-primary">
                <Inbox className="h-7 w-7" />
            </div>
            <div>
                <h3 className="text-display">
                    {hasFilter ? "Keine Treffer" : "Noch keine Incidents"}
                </h3>
                <p className="mt-1 max-w-md text-body text-muted-foreground">
                    {hasFilter
                        ? "Passe Suche oder Filter an, um weitere Eintraege zu sehen."
                        : "Lege einen neuen Incident an oder starte zum Testen einen Demo-Incident mit Vordaten."}
                </p>
            </div>
            {!hasFilter && (
                <div className="flex flex-wrap justify-center gap-2">
                    <Button onClick={onNew} data-testid="empty-new">
                        <Plus className="h-4 w-4" />
                        Incident anlegen
                    </Button>
                    <Button
                        variant="outline"
                        onClick={onDemo}
                        data-testid="empty-demo"
                    >
                        <PlayCircle className="h-4 w-4" />
                        Demo starten
                    </Button>
                </div>
            )}
        </div>
    );
}

export default function IncidentList() {
    const {
        incidents,
        loading,
        error,
        activeId,
        setActive,
        refresh,
        create,
        startDemo,
        closeIncident,
        reopenIncident,
        remove
    } = useIncidents();
    const navigate = useNavigate();
    const { registerCommand } = useCommandPalette();

    const [filter, setFilter] = React.useState("alle");
    const [query, setQuery] = React.useState("");
    const [newOpen, setNewOpen] = React.useState(false);
    const [demoBusy, setDemoBusy] = React.useState(false);
    const [confirmDelete, setConfirmDelete] = React.useState(null);

    const filtered = React.useMemo(() => {
        const f = FILTERS.find((x) => x.key === filter) || FILTERS[0];
        const q = query.trim().toLowerCase();
        return incidents
            .filter(f.match)
            .filter((i) =>
                q
                    ? `${i.name} ${i.ort || ""} ${i.typ}`
                          .toLowerCase()
                          .includes(q)
                    : true
            );
    }, [incidents, filter, query]);

    const counts = React.useMemo(() => {
        const c = {};
        for (const f of FILTERS) c[f.key] = incidents.filter(f.match).length;
        return c;
    }, [incidents]);

    const handleOpen = React.useCallback(
        (incident) => {
            setActive(incident.id);
            navigate("/lage");
        },
        [navigate, setActive]
    );

    const handleActivate = React.useCallback(
        (incident) => setActive(incident.id),
        [setActive]
    );

    const handleDemo = React.useCallback(async () => {
        setDemoBusy(true);
        try {
            const created = await startDemo();
            return created;
        } finally {
            setDemoBusy(false);
        }
    }, [startDemo]);

    // Dynamische Commands: "Incident wechseln" fuer jeden Incident
    React.useEffect(() => {
        const unregisters = [];
        for (const i of incidents) {
            unregisters.push(
                registerCommand({
                    id: `incident-switch-${i.id}`,
                    label: `Wechseln zu: ${i.name}${i.demo ? " (DEMO)" : ""}`,
                    group: "Incident wechseln",
                    keywords: [i.typ, i.ort || "", i.id],
                    run: () => handleOpen(i)
                })
            );
        }
        return () => unregisters.forEach((u) => u && u());
    }, [incidents, registerCommand, handleOpen]);

    return (
        <div className="mx-auto w-full max-w-[1600px] px-6 py-6">
            {/* Kopfzeile */}
            <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
                <div>
                    <div className="text-caption uppercase tracking-wider text-muted-foreground">
                        Schritt 02 · Einstieg
                    </div>
                    <h1
                        className="mt-1 text-display"
                        data-testid="incident-list-title"
                    >
                        Incidents
                    </h1>
                    <p className="mt-1 max-w-2xl text-body text-muted-foreground">
                        Waehle einen bestehenden Incident oder lege einen neuen
                        an. Der aktive Incident erscheint im Global-Header und
                        ist die Grundlage fuer alle weiteren Module.
                    </p>
                </div>
                <div className="flex flex-wrap gap-2">
                    <Button
                        variant="outline"
                        onClick={handleDemo}
                        disabled={demoBusy}
                        data-testid="btn-demo"
                    >
                        <PlayCircle className="h-4 w-4" />
                        {demoBusy ? "Starte…" : "Demo-Incident starten"}
                    </Button>
                    <Button
                        onClick={() => setNewOpen(true)}
                        data-testid="btn-new"
                    >
                        <Plus className="h-4 w-4" />
                        Neuen Incident anlegen
                    </Button>
                </div>
            </div>

            {/* Filter- & Suchleiste */}
            <div className="mb-4 flex flex-wrap items-center gap-3 rounded-md border border-border bg-surface-sunken px-3 py-2.5">
                <div className="flex flex-wrap gap-2">
                    {FILTERS.map((f) => (
                        <FilterChip
                            key={f.key}
                            active={filter === f.key}
                            tone={f.tone || "neutral"}
                            count={counts[f.key]}
                            onToggle={() => setFilter(f.key)}
                            data-testid={`filter-${f.key}`}
                        >
                            {f.label}
                        </FilterChip>
                    ))}
                </div>
                <div className="ml-auto flex items-center gap-2">
                    <div className="relative">
                        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                        <Input
                            type="search"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            placeholder="Suche (Name, Ort, Typ)…"
                            className="h-8 w-64 bg-background pl-8"
                            data-testid="incident-search"
                        />
                    </div>
                    <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={refresh}
                        title="Neu laden"
                        data-testid="btn-refresh"
                    >
                        <RefreshCw className="h-4 w-4" />
                    </Button>
                </div>
            </div>

            {error && (
                <div
                    className="mb-4 rounded-md border border-status-red/40 bg-status-red/10 px-3 py-2 text-caption text-status-red"
                    data-testid="incident-list-error"
                >
                    {error}
                </div>
            )}

            {/* Liste */}
            {loading ? (
                <IncidentListSkeleton />
            ) : filtered.length === 0 ? (
                <EmptyState
                    hasFilter={query !== "" || filter !== "alle"}
                    onNew={() => setNewOpen(true)}
                    onDemo={handleDemo}
                />
            ) : (
                <div
                    className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"
                    data-testid="incident-grid"
                >
                    {filtered.map((i) => (
                        <IncidentCard
                            key={i.id}
                            incident={i}
                            active={activeId === i.id}
                            onActivate={handleActivate}
                            onOpen={handleOpen}
                            onClose={(x) => closeIncident(x.id)}
                            onReopen={(x) => reopenIncident(x.id)}
                            onDelete={(x) => setConfirmDelete(x)}
                        />
                    ))}
                </div>
            )}

            {/* Fusszeile: Hint Palette */}
            <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-surface-sunken px-4 py-2.5 text-caption text-muted-foreground">
                <div className="flex items-center gap-2">
                    <StatusBadge tone="info" variant="soft" size="sm">
                        Tipp
                    </StatusBadge>
                    <span>
                        Schneller Wechsel zwischen Incidents und Modulen via
                        Kommando-Palette.
                    </span>
                </div>
                <div className="flex items-center gap-2">
                    <kbd className="inline-flex h-6 items-center gap-1 rounded border border-border bg-background px-2 font-mono text-[0.7rem]">
                        <CommandIcon className="h-3 w-3" />
                        K
                    </kbd>
                    <span>oeffnet die Palette</span>
                </div>
            </div>

            <NewIncidentDialog
                open={newOpen}
                onOpenChange={setNewOpen}
                onCreate={create}
            />

            <ConfirmModal
                open={confirmDelete !== null}
                onOpenChange={(v) => !v && setConfirmDelete(null)}
                title="Demo-Incident loeschen?"
                description={
                    confirmDelete
                        ? `"${confirmDelete.name}" wird unwiderruflich entfernt. Nur Demo-Incidents koennen so geloescht werden.`
                        : ""
                }
                confirmLabel="Loeschen"
                tone="destructive"
                onConfirm={() => {
                    if (confirmDelete) remove(confirmDelete.id);
                    setConfirmDelete(null);
                }}
            />
        </div>
    );
}
