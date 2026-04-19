import * as React from "react";
import { cn } from "@/lib/utils";
import { StatusBadge } from "@/components/primitives/StatusBadge";
import { Button } from "@/components/ui/button";
import {
    MapPin,
    Clock,
    Calendar,
    PartyPopper,
    Stethoscope,
    GraduationCap,
    Siren,
    Boxes,
    ChevronRight,
    LogIn,
    XCircle,
    RotateCcw,
    Trash2
} from "lucide-react";
import { formatDuration, formatDateTime } from "@/lib/time";

const TYP_META = {
    veranstaltung: { label: "Veranstaltung", icon: PartyPopper },
    sanitaetsdienst: { label: "Sanitaetsdienst", icon: Stethoscope },
    uebung: { label: "Uebung", icon: GraduationCap },
    einsatz: { label: "Einsatz", icon: Siren },
    sonstiges: { label: "Sonstiges", icon: Boxes }
};

const STATUS_META = {
    geplant: { label: "Geplant", tone: "gray" },
    operativ: { label: "Operativ", tone: "green" },
    abgeschlossen: { label: "Abgeschlossen", tone: "gray" },
    archiviert: { label: "Archiviert", tone: "neutral" }
};

/**
 * IncidentCard – Uebersichtskarte mit Name, Typ, Dauer, Status, DEMO-Badge.
 * Props:
 *   incident, active, onActivate, onOpen, onClose, onReopen, onDelete
 */
export function IncidentCard({
    incident,
    active = false,
    onActivate,
    onOpen,
    onClose,
    onReopen,
    onDelete
}) {
    const typ = TYP_META[incident.typ] || TYP_META.sonstiges;
    const TypIcon = typ.icon;
    const status = STATUS_META[incident.status] || STATUS_META.geplant;

    // Live-Dauer nur bei operativ & ohne end_at
    const [now, setNow] = React.useState(() => new Date());
    React.useEffect(() => {
        if (incident.status !== "operativ") return undefined;
        const id = setInterval(() => setNow(new Date()), 30 * 1000);
        return () => clearInterval(id);
    }, [incident.status]);

    const duration = React.useMemo(() => {
        const end = incident.end_at ? new Date(incident.end_at) : now;
        const start = new Date(incident.start_at);
        return formatDuration(end - start);
    }, [incident.start_at, incident.end_at, now]);

    const isClosed =
        incident.status === "abgeschlossen" || incident.status === "archiviert";

    return (
        <article
            data-testid={`incident-card-${incident.id}`}
            data-active={active}
            className={cn(
                "els-surface relative flex flex-col overflow-hidden transition-all",
                "hover:border-primary/60 hover:shadow-[0_0_0_1px_hsl(var(--primary)/0.3)]",
                active && "border-primary/80 ring-1 ring-primary/30"
            )}
        >
            {/* aktiv-Marker links */}
            {active && (
                <span
                    aria-hidden
                    className="absolute left-0 top-0 h-full w-1 bg-primary"
                />
            )}

            <div className="flex items-start gap-3 border-b border-border p-4">
                <div
                    className={cn(
                        "flex h-10 w-10 shrink-0 items-center justify-center rounded-md",
                        "bg-primary/10 text-primary"
                    )}
                >
                    <TypIcon className="h-5 w-5" />
                </div>

                <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                        <h3
                            className="text-heading truncate"
                            title={incident.name}
                            data-testid="incident-card-name"
                        >
                            {incident.name}
                        </h3>
                        {incident.demo && (
                            <StatusBadge
                                tone="yellow"
                                variant="solid"
                                size="sm"
                                data-testid="incident-card-demo-badge"
                            >
                                DEMO
                            </StatusBadge>
                        )}
                    </div>
                    <div className="mt-0.5 flex items-center gap-2 text-caption text-muted-foreground">
                        <span>{typ.label}</span>
                        <span aria-hidden>·</span>
                        <span className="font-mono" title="Incident-ID">
                            {incident.id.slice(0, 8)}
                        </span>
                    </div>
                </div>

                <StatusBadge
                    tone={status.tone}
                    variant="soft"
                    size="sm"
                    dot={incident.status === "operativ"}
                >
                    {status.label}
                </StatusBadge>
            </div>

            <div className="flex-1 space-y-2 p-4">
                <div className="flex items-center gap-2 text-body">
                    <MapPin className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="truncate">
                        {incident.ort || (
                            <span className="italic text-muted-foreground">
                                kein Ort
                            </span>
                        )}
                    </span>
                </div>
                <div className="flex items-center gap-2 text-body">
                    <Calendar className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <span
                        className="font-mono text-caption"
                        data-testid="incident-card-start"
                    >
                        {formatDateTime(incident.start_at)}
                    </span>
                </div>
                <div className="flex items-center gap-2 text-body">
                    <Clock className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="text-caption text-muted-foreground">
                        Dauer
                    </span>
                    <span
                        className="font-mono tabular-nums"
                        data-testid="incident-card-duration"
                    >
                        {duration}
                    </span>
                    {incident.status === "operativ" && (
                        <span className="ml-1 h-1.5 w-1.5 rounded-full bg-status-green animate-pulse-ring" />
                    )}
                </div>
            </div>

            <div className="flex items-center justify-between gap-2 border-t border-border bg-surface-sunken px-3 py-2">
                <div className="flex items-center gap-1">
                    {isClosed ? (
                        <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            onClick={() => onReopen?.(incident)}
                            data-testid={`incident-reopen-${incident.id}`}
                            title="Wieder aktivieren"
                        >
                            <RotateCcw className="h-3.5 w-3.5" />
                            Reaktivieren
                        </Button>
                    ) : (
                        !active && (
                            <Button
                                type="button"
                                size="sm"
                                variant="ghost"
                                onClick={() => onActivate?.(incident)}
                                data-testid={`incident-activate-${incident.id}`}
                            >
                                <LogIn className="h-3.5 w-3.5" />
                                Aktivieren
                            </Button>
                        )
                    )}
                    {incident.status === "operativ" && (
                        <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            onClick={() => onClose?.(incident)}
                            data-testid={`incident-close-${incident.id}`}
                        >
                            <XCircle className="h-3.5 w-3.5" />
                            Abschliessen
                        </Button>
                    )}
                    {incident.demo && (
                        <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            onClick={() => onDelete?.(incident)}
                            data-testid={`incident-delete-${incident.id}`}
                            className="text-muted-foreground hover:text-destructive"
                        >
                            <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                    )}
                </div>
                <Button
                    type="button"
                    size="sm"
                    variant={active ? "default" : "outline"}
                    onClick={() => onOpen?.(incident)}
                    data-testid={`incident-open-${incident.id}`}
                >
                    Lage oeffnen
                    <ChevronRight className="h-4 w-4" />
                </Button>
            </div>
        </article>
    );
}
