import * as React from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/primitives";
import { IncidentCard } from "@/components/incidents/IncidentCard";
import { DeleteArchivModal } from "@/components/incidents/DeleteArchivModal";
import { useIncidents } from "@/context/IncidentContext";
import { useRole } from "@/context/RoleContext";
import {
    Search,
    RefreshCw,
    Archive,
    ArrowLeft,
    Inbox,
    Lock
} from "lucide-react";
import { toast } from "sonner";

function ArchivSkeleton() {
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

function EmptyArchiv() {
    const navigate = useNavigate();
    return (
        <div
            className="els-surface flex flex-col items-center gap-4 py-16 px-6 text-center"
            data-testid="archiv-empty"
        >
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 text-primary">
                <Inbox className="h-7 w-7" />
            </div>
            <div>
                <h3 className="text-display">Archiv ist leer</h3>
                <p className="mt-1 max-w-md text-body text-muted-foreground">
                    Abgeschlossene Incidents erscheinen hier. Sobald ein Einsatz
                    freigegeben und abgeschlossen wird, wandert er automatisch in
                    das Archiv.
                </p>
            </div>
            <Button onClick={() => navigate("/")} data-testid="archiv-back">
                <ArrowLeft className="h-4 w-4" />
                Zur Einstiegs-Uebersicht
            </Button>
        </div>
    );
}

export default function ArchivPage() {
    const {
        incidents,
        loading,
        error,
        activeId,
        setActive,
        refresh,
        reopenIncident,
        remove
    } = useIncidents();
    const navigate = useNavigate();
    const { can, role } = useRole();

    const [query, setQuery] = React.useState("");
    const [confirmDelete, setConfirmDelete] = React.useState(null);

    const canDelete = role === "einsatzleiter";
    const canReopen = can("incident.close"); // einsatzleiter only

    const archived = React.useMemo(() => {
        const q = query.trim().toLowerCase();
        return incidents
            .filter((i) => i.status === "abgeschlossen")
            .filter((i) =>
                q
                    ? `${i.name} ${i.ort || ""} ${i.typ}`
                          .toLowerCase()
                          .includes(q)
                    : true
            );
    }, [incidents, query]);

    const handleOpen = React.useCallback(
        (incident) => {
            setActive(incident.id);
            navigate("/abschluss");
        },
        [navigate, setActive]
    );

    const handleReopen = React.useCallback(
        async (incident) => {
            if (!canReopen) return;
            try {
                await reopenIncident(incident.id);
                toast.success("Incident reaktiviert");
                setActive(incident.id);
                navigate("/lage");
            } catch (e) {
                toast.error("Reaktivieren fehlgeschlagen");
            }
        },
        [canReopen, reopenIncident, setActive, navigate]
    );

    const handleDelete = React.useCallback(async () => {
        if (!confirmDelete) return;
        try {
            await remove(confirmDelete.id);
            toast.success("Incident endgueltig geloescht");
        } catch (e) {
            toast.error("Loeschen fehlgeschlagen");
        } finally {
            setConfirmDelete(null);
        }
    }, [confirmDelete, remove]);

    return (
        <div className="mx-auto w-full max-w-[1600px] px-6 py-6">
            {/* Kopfzeile */}
            <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
                <div>
                    <div className="text-caption uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                        <Archive className="h-3.5 w-3.5" />
                        Archiv
                        <StatusBadge tone="gray" variant="soft" size="sm">
                            <Lock className="h-3 w-3" />
                            nur Lesen
                        </StatusBadge>
                    </div>
                    <h1
                        className="mt-1 text-display"
                        data-testid="archiv-title"
                    >
                        Abgeschlossene Einsaetze
                    </h1>
                    <p className="mt-1 max-w-2xl text-body text-muted-foreground">
                        Abgeschlossene Incidents werden hier lesend gehalten.
                        Loeschen ist nur durch den Einsatzleiter nach bestaetigter
                        Texteingabe moeglich.
                    </p>
                </div>
                <Button
                    variant="outline"
                    onClick={() => navigate("/")}
                    data-testid="archiv-back-top"
                >
                    <ArrowLeft className="h-4 w-4" />
                    Zurueck zum Einstieg
                </Button>
            </div>

            {/* Such- und Filterleiste */}
            <div className="mb-4 flex flex-wrap items-center gap-3 rounded-md border border-border bg-surface-sunken px-3 py-2.5">
                <StatusBadge tone="neutral" variant="soft" size="sm">
                    {archived.length} archiviert
                </StatusBadge>
                <div className="ml-auto flex items-center gap-2">
                    <div className="relative">
                        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                        <Input
                            type="search"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            placeholder="Suche (Name, Ort, Typ)…"
                            className="h-8 w-64 bg-background pl-8"
                            data-testid="archiv-search"
                        />
                    </div>
                    <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={refresh}
                        title="Neu laden"
                        data-testid="archiv-refresh"
                    >
                        <RefreshCw className="h-4 w-4" />
                    </Button>
                </div>
            </div>

            {error && (
                <div
                    className="mb-4 rounded-md border border-status-red/40 bg-status-red/10 px-3 py-2 text-caption text-status-red"
                    data-testid="archiv-error"
                >
                    {error}
                </div>
            )}

            {/* Liste */}
            {loading ? (
                <ArchivSkeleton />
            ) : archived.length === 0 ? (
                <EmptyArchiv />
            ) : (
                <div
                    className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"
                    data-testid="archiv-grid"
                >
                    {archived.map((i) => (
                        <IncidentCard
                            key={i.id}
                            incident={i}
                            active={activeId === i.id}
                            variant="archive"
                            openLabel="Lesen"
                            showDelete={canDelete}
                            showReopen={canReopen}
                            onOpen={handleOpen}
                            onReopen={handleReopen}
                            onDelete={(x) => setConfirmDelete(x)}
                        />
                    ))}
                </div>
            )}

            <DeleteArchivModal
                open={confirmDelete !== null}
                onOpenChange={(v) => !v && setConfirmDelete(null)}
                incident={confirmDelete}
                onConfirm={handleDelete}
            />
        </div>
    );
}
