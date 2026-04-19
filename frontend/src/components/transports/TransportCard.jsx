import * as React from "react";
import { cn } from "@/lib/utils";
import { StatusBadge, SichtungBadge } from "@/components/primitives";
import { Button } from "@/components/ui/button";
import {
    Truck,
    MapPin,
    Clock,
    Play,
    CheckCircle2,
    Trash2,
    ArrowRight,
    X
} from "lucide-react";
import { TRANSPORT_ZIEL, TRANSPORT_STATUS } from "@/lib/transport-meta";
import { formatDuration } from "@/lib/time";

/**
 * TransportCard – kompakt, draggable, mit Status-Aktionen.
 */
export function TransportCard({
    transport,
    onDragStart,
    onAssign,
    onStart,
    onComplete,
    onUnassign,
    onDelete,
    onOpenPatient
}) {
    const statusMeta =
        TRANSPORT_STATUS[transport.status] || { label: transport.status, tone: "neutral" };
    const ziel = TRANSPORT_ZIEL[transport.ziel] || { label: transport.ziel };

    // Live-Dauer: seit created_at oder seit letztem Status-Wechsel
    const [now, setNow] = React.useState(Date.now());
    React.useEffect(() => {
        if (transport.status === "abgeschlossen") return undefined;
        const id = setInterval(() => setNow(Date.now()), 30 * 1000);
        return () => clearInterval(id);
    }, [transport.status]);

    const startRef =
        transport.status === "abgeschlossen"
            ? transport.abgeschlossen_at
            : transport.status === "unterwegs"
                ? transport.gestartet_at
                : transport.status === "zugewiesen"
                    ? transport.zugewiesen_at
                    : transport.created_at;

    const duration = React.useMemo(() => {
        if (!startRef) return "–";
        const end =
            transport.status === "abgeschlossen" && transport.abgeschlossen_at
                ? new Date(transport.abgeschlossen_at).getTime()
                : now;
        return formatDuration(end - new Date(startRef).getTime());
    }, [startRef, transport.abgeschlossen_at, transport.status, now]);

    const draggable =
        transport.status !== "abgeschlossen" && transport.status !== "unterwegs";

    return (
        <article
            draggable={draggable}
            onDragStart={(e) => {
                if (!draggable) {
                    e.preventDefault();
                    return;
                }
                e.dataTransfer.effectAllowed = "move";
                e.dataTransfer.setData("text/transport-id", transport.id);
                e.dataTransfer.setData("text/transport-typ", transport.typ);
                onDragStart?.(transport);
            }}
            data-testid={`transport-card-${transport.id}`}
            data-status={transport.status}
            className={cn(
                "els-surface group relative flex flex-col gap-2 p-3 transition-colors",
                draggable && "cursor-grab active:cursor-grabbing hover:border-primary/60",
                transport.status === "abgeschlossen" && "opacity-70"
            )}
        >
            <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                    {transport.patient_sichtung && (
                        <SichtungBadge level={transport.patient_sichtung} size="sm" />
                    )}
                    {transport.patient_kennung ? (
                        <button
                            type="button"
                            onClick={() => onOpenPatient?.(transport)}
                            className="font-mono font-semibold text-body truncate els-focus-ring"
                            title="Zum Patienten"
                            data-testid={`transport-card-${transport.id}-patient`}
                        >
                            {transport.patient_kennung}
                        </button>
                    ) : (
                        <span className="text-caption text-muted-foreground italic">
                            ohne Patient
                        </span>
                    )}
                </div>
                <StatusBadge
                    tone={statusMeta.tone}
                    variant="soft"
                    size="sm"
                    dot={transport.status === "unterwegs" || transport.status === "offen"}
                >
                    {statusMeta.label}
                </StatusBadge>
            </div>

            <div className="flex items-center gap-1.5 text-caption">
                <MapPin className="h-3 w-3 text-muted-foreground" />
                <span className="text-muted-foreground">Ziel:</span>
                <span className="font-medium truncate">{ziel.label}</span>
            </div>

            <div className="flex items-center gap-1.5 text-caption">
                <Truck className="h-3 w-3 text-muted-foreground" />
                <span className="text-muted-foreground">Ressource:</span>
                {transport.ressource ? (
                    <span
                        className="font-medium truncate"
                        data-testid={`transport-card-${transport.id}-resource`}
                    >
                        {transport.ressource}
                    </span>
                ) : (
                    <span className="text-status-yellow font-medium">
                        — fehlt
                    </span>
                )}
                {transport.ressource && transport.status === "zugewiesen" && (
                    <button
                        type="button"
                        onClick={() => onUnassign?.(transport)}
                        data-testid={`transport-card-${transport.id}-unassign`}
                        className="ml-auto p-0.5 text-muted-foreground hover:text-destructive"
                        title="Ressource entfernen"
                    >
                        <X className="h-3 w-3" />
                    </button>
                )}
            </div>

            <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1 text-caption text-muted-foreground">
                    <Clock className="h-3 w-3" />
                    <span className="font-mono tabular-nums" data-testid={`transport-card-${transport.id}-duration`}>
                        {duration}
                    </span>
                </div>
                <div className="flex items-center gap-1">
                    {transport.status === "offen" && (
                        <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => onAssign?.(transport)}
                            className="h-6 px-2 text-caption"
                            data-testid={`transport-card-${transport.id}-assign`}
                        >
                            Ressource …
                        </Button>
                    )}
                    {transport.status === "zugewiesen" && (
                        <Button
                            type="button"
                            size="sm"
                            onClick={() => onStart?.(transport)}
                            className="h-6 px-2 text-caption"
                            data-testid={`transport-card-${transport.id}-start`}
                        >
                            <Play className="h-3 w-3" />
                            Abfahrt
                        </Button>
                    )}
                    {transport.status === "unterwegs" && (
                        <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => onComplete?.(transport)}
                            className="h-6 px-2 text-caption"
                            data-testid={`transport-card-${transport.id}-complete`}
                        >
                            <CheckCircle2 className="h-3 w-3" />
                            Abschliessen
                        </Button>
                    )}
                    <button
                        type="button"
                        onClick={() => onDelete?.(transport)}
                        className="p-1 text-muted-foreground hover:text-destructive"
                        title="Loeschen"
                        data-testid={`transport-card-${transport.id}-delete`}
                    >
                        <Trash2 className="h-3 w-3" />
                    </button>
                </div>
            </div>
        </article>
    );
}
