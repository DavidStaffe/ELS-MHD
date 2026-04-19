import * as React from "react";
import { cn } from "@/lib/utils";
import { formatDuration, formatDateTime } from "@/lib/time";
import { Check, Clock3 } from "lucide-react";

const DEFAULT_EVENTS = [
    { key: "created_at", label: "Ankunft" },
    { key: "sichtung_at", label: "Sichtung" },
    { key: "behandlung_start_at", label: "Behandlungsstart" },
    { key: "transport_angefordert_at", label: "Transport angefordert" },
    { key: "fallabschluss_at", label: "Fallabschluss" }
];

/**
 * PatientTimeline – vertikale Ereignis-Timeline mit Dauer-Deltas.
 */
export function PatientTimeline({ patient, events = DEFAULT_EVENTS }) {
    const [now, setNow] = React.useState(() => Date.now());
    React.useEffect(() => {
        const closed =
            patient.status === "uebergeben" || patient.status === "entlassen";
        if (closed) return undefined;
        const id = setInterval(() => setNow(Date.now()), 30 * 1000);
        return () => clearInterval(id);
    }, [patient.status]);

    // Erzeuge Zeitreihe: pro Event {ts, label, delta-to-prev}
    const items = [];
    let prevTs = null;
    for (const ev of events) {
        const ts = patient[ev.key] ? new Date(patient[ev.key]).getTime() : null;
        items.push({
            ...ev,
            ts,
            delta: ts && prevTs ? ts - prevTs : null
        });
        if (ts) prevTs = ts;
    }

    return (
        <ol className="relative space-y-3" data-testid="patient-timeline">
            {items.map((it, i) => {
                const done = it.ts !== null;
                const isNext = !done && items.slice(0, i).every((x) => x.ts !== null);
                return (
                    <li
                        key={it.key}
                        data-testid={`timeline-${it.key}`}
                        className="flex items-start gap-3"
                    >
                        <div className="relative flex h-5 w-5 shrink-0 items-center justify-center">
                            <span
                                className={cn(
                                    "block h-2.5 w-2.5 rounded-full",
                                    done
                                        ? "bg-primary"
                                        : isNext
                                            ? "bg-status-yellow animate-pulse-ring"
                                            : "bg-muted"
                                )}
                            />
                            {i < items.length - 1 && (
                                <span
                                    aria-hidden
                                    className={cn(
                                        "absolute left-1/2 top-5 h-[calc(100%+0.5rem)] w-px -translate-x-1/2",
                                        done ? "bg-primary/40" : "bg-border"
                                    )}
                                />
                            )}
                        </div>
                        <div className="flex-1 pb-1 text-body">
                            <div className="flex items-center justify-between gap-2">
                                <span
                                    className={cn(
                                        "font-medium",
                                        done
                                            ? "text-foreground"
                                            : "text-muted-foreground"
                                    )}
                                >
                                    {it.label}
                                </span>
                                {done ? (
                                    <Check className="h-3.5 w-3.5 text-primary" />
                                ) : isNext ? (
                                    <Clock3 className="h-3.5 w-3.5 text-status-yellow" />
                                ) : null}
                            </div>
                            <div className="flex items-center gap-2 text-caption text-muted-foreground">
                                {it.ts ? (
                                    <>
                                        <span className="font-mono">
                                            {formatDateTime(it.ts)}
                                        </span>
                                        {it.delta != null && (
                                            <span className="rounded bg-surface-raised px-1.5 py-0.5 font-mono tabular-nums">
                                                +
                                                {formatDuration(it.delta)}
                                            </span>
                                        )}
                                    </>
                                ) : (
                                    <span>offen</span>
                                )}
                            </div>
                        </div>
                    </li>
                );
            })}

            {/* Wiedereroeffnungs-Historie */}
            {(patient.wiedereroeffnet_at || []).map((ts, idx) => (
                <li
                    key={`reopen-${idx}`}
                    data-testid={`timeline-reopen-${idx}`}
                    className="flex items-start gap-3"
                >
                    <div className="relative flex h-5 w-5 shrink-0 items-center justify-center">
                        <span className="block h-2.5 w-2.5 rounded-full bg-status-yellow" />
                    </div>
                    <div className="flex-1 text-body">
                        <div className="flex items-center justify-between gap-2">
                            <span className="font-medium text-status-yellow">
                                Wiedereroeffnet #{idx + 1}
                            </span>
                        </div>
                        <div className="text-caption text-muted-foreground">
                            <span className="font-mono">{formatDateTime(ts)}</span>
                        </div>
                    </div>
                </li>
            ))}

            {/* Live-Dauer seit letztem Event (wenn nicht abgeschlossen) */}
            {patient.status !== "uebergeben" &&
                patient.status !== "entlassen" &&
                prevTs && (
                    <li
                        className="flex items-start gap-3"
                        data-testid="timeline-live"
                    >
                        <div className="flex h-5 w-5 shrink-0 items-center justify-center">
                            <span className="block h-1.5 w-1.5 rounded-full bg-muted" />
                        </div>
                        <div className="text-caption text-muted-foreground">
                            seit letztem Ereignis ·
                            <span className="ml-1 font-mono tabular-nums">
                                {formatDuration(now - prevTs)}
                            </span>
                        </div>
                    </li>
                )}
        </ol>
    );
}
