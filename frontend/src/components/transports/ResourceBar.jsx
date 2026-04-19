import * as React from "react";
import { cn } from "@/lib/utils";
import { Truck, Plus } from "lucide-react";
import { RESOURCE_POOL, occupiedResources } from "@/lib/transport-meta";

/**
 * ResourceBar – Drop-Targets fuer Transport-Zuweisung.
 * Sticky am unteren Bildschirmrand; Drag einer TransportCard auf eine Ressource
 * ruft onAssign(transportId, ressourceName) auf.
 */
export function ResourceBar({
    transports = [],
    onAssign,
    onNewTransport,
    className
}) {
    const occupied = React.useMemo(
        () => occupiedResources(transports),
        [transports]
    );
    const [overId, setOverId] = React.useState(null);
    const [overTyp, setOverTyp] = React.useState(null);

    const makeHandlers = (resource) => ({
        onDragOver: (e) => {
            const dragTyp = e.dataTransfer.types.includes("text/transport-typ");
            e.preventDefault();
            e.dataTransfer.dropEffect = "move";
            setOverId(resource.id);
        },
        onDragLeave: () => setOverId((id) => (id === resource.id ? null : id)),
        onDrop: (e) => {
            e.preventDefault();
            const tid = e.dataTransfer.getData("text/transport-id");
            const typ = e.dataTransfer.getData("text/transport-typ");
            setOverId(null);
            setOverTyp(null);
            if (!tid) return;
            if (typ && typ !== resource.typ) {
                // Typ-Mismatch (intern vs. extern) -> nicht zulassen
                return;
            }
            onAssign?.(tid, resource.name);
        }
    });

    const renderGroup = (typ) => {
        const list = RESOURCE_POOL[typ] || [];
        return (
            <div className="flex flex-1 flex-col gap-1.5">
                <div className="text-[0.7rem] uppercase tracking-wider text-muted-foreground">
                    {typ === "intern" ? "Intern (UHS)" : "Extern (RD/KH)"}
                </div>
                <div className="flex flex-wrap gap-2">
                    {list.map((r) => {
                        const busy = occupied.get(r.name) || [];
                        const over = overId === r.id;
                        const disabled = overTyp && overTyp !== r.typ;
                        return (
                            <div
                                key={r.id}
                                {...makeHandlers(r)}
                                onDragEnter={(e) => {
                                    const dragTyp = e.dataTransfer.types.includes("text/transport-typ")
                                        ? e.dataTransfer.getData("text/transport-typ")
                                        : null;
                                    if (dragTyp) setOverTyp(dragTyp);
                                }}
                                data-testid={`resource-drop-${r.id}`}
                                data-busy={busy.length > 0}
                                className={cn(
                                    "flex min-w-[8rem] items-center gap-2 rounded-md border px-2.5 py-1.5 text-caption transition-colors",
                                    "bg-surface-raised",
                                    busy.length === 0
                                        ? "border-border"
                                        : "border-primary/40 bg-primary/10",
                                    over && "ring-2 ring-primary bg-primary/15",
                                    disabled && "opacity-40"
                                )}
                            >
                                <Truck
                                    className={cn(
                                        "h-3.5 w-3.5",
                                        busy.length > 0 ? "text-primary" : "text-muted-foreground"
                                    )}
                                />
                                <span className="font-medium">{r.name}</span>
                                {busy.length > 0 && (
                                    <span className="ml-auto rounded bg-primary/20 px-1.5 font-mono text-[0.65rem] text-primary">
                                        {busy.length}
                                    </span>
                                )}
                            </div>
                        );
                    })}
                </div>
            </div>
        );
    };

    return (
        <div
            data-testid="resource-bar"
            className={cn(
                "sticky bottom-0 z-20 border-t border-border bg-surface-sunken/95 px-4 py-3 backdrop-blur",
                className
            )}
        >
            <div className="flex items-start gap-6">
                {renderGroup("intern")}
                <div className="h-12 w-px bg-border" aria-hidden />
                {renderGroup("extern")}
                {/* Spacer fuer Made-with-Emergent Badge */}
                <div aria-hidden className="hidden md:block w-44 shrink-0" />
            </div>
            <div className="mt-2 flex items-center justify-between gap-2 text-[0.7rem] text-muted-foreground">
                <span>
                    Drag &amp; Drop: Transport-Karte auf Ressource ziehen.
                    Typ (intern / extern) muss passen.
                </span>
                {onNewTransport && (
                    <button
                        type="button"
                        onClick={onNewTransport}
                        data-testid="resource-bar-new-transport"
                        className="inline-flex items-center gap-1 rounded border border-border bg-background px-2 py-1 text-[0.7rem] text-foreground hover:border-primary/60"
                    >
                        <Plus className="h-3 w-3" />
                        Transport manuell anlegen
                    </button>
                )}
            </div>
        </div>
    );
}
