import * as React from "react";
import { cn } from "@/lib/utils";
import { StatusBadge } from "@/components/primitives/StatusBadge";
import { Button } from "@/components/ui/button";
import { CommandPaletteTrigger } from "@/components/command/CommandPalette";
import { formatDuration } from "@/lib/time";
import { useRole, ROLES } from "@/context/RoleContext";
import { Sun, Moon, ShieldCheck, Stethoscope, FileCheck2, Clock3, LayoutGrid, UserCog, Radio, Layers } from "lucide-react";

const ROLE_ICON = {
    einsatzleiter: ShieldCheck,
    fuehrungsassistenz: Radio,
    abschnittleitung: Layers,
    helfer: Stethoscope,
    dokumentar: FileCheck2
};

function useClock(intervalMs = 1000) {
    const [now, setNow] = React.useState(() => new Date());
    React.useEffect(() => {
        const id = setInterval(() => setNow(new Date()), intervalMs);
        return () => clearInterval(id);
    }, [intervalMs]);
    return now;
}

function formatTime(d) {
    return d.toLocaleTimeString("de-DE", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
    });
}
function formatDate(d) {
    return d.toLocaleDateString("de-DE", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric"
    });
}

const STATUS_MAP = {
    operativ: { label: "Operativ", tone: "green" },
    geplant: { label: "Geplant", tone: "gray" },
    abgeschlossen: { label: "Abgeschlossen", tone: "gray" },
    archiviert: { label: "Archiviert", tone: "neutral" }
};

export function GlobalHeader({
    incident,
    theme,
    onToggleTheme,
    onGoToIncidents,
    className
}) {
    const now = useClock(1000);
    const { roleMeta, setPickerOpen } = useRole();

    // Live-Dauer seit Incident-Start
    const duration = React.useMemo(() => {
        if (!incident?.start_at) return null;
        const end = incident.end_at ? new Date(incident.end_at) : now;
        return formatDuration(end - new Date(incident.start_at));
    }, [incident, now]);

    const statusMeta = incident ? STATUS_MAP[incident.status] : null;

    return (
        <header
            data-testid="app-header"
            className={cn(
                "flex h-header items-center gap-4 border-b border-border bg-surface-sunken/80 backdrop-blur px-4",
                className
            )}
        >
            {/* Incident-Kontext */}
            <div className="flex min-w-0 flex-1 items-center gap-3">
                {incident ? (
                    <>
                        <div className="relative">
                            <span
                                className={cn(
                                    "block h-2.5 w-2.5 rounded-full",
                                    incident.status === "operativ"
                                        ? "bg-status-green"
                                        : "bg-status-gray"
                                )}
                            />
                            {incident.status === "operativ" && (
                                <span
                                    aria-hidden
                                    className="absolute inset-0 rounded-full bg-status-green animate-pulse-ring"
                                />
                            )}
                        </div>
                        <button
                            type="button"
                            onClick={onGoToIncidents}
                            className="min-w-0 text-left els-focus-ring"
                            title="Zur Incident-Uebersicht"
                            data-testid="header-incident-button"
                        >
                            <div className="flex items-center gap-2">
                                <span
                                    className="text-heading truncate"
                                    data-testid="header-incident-name"
                                >
                                    {incident.name}
                                </span>
                                {incident.demo && (
                                    <StatusBadge
                                        tone="yellow"
                                        variant="solid"
                                        size="sm"
                                        data-testid="header-demo-badge"
                                    >
                                        DEMO
                                    </StatusBadge>
                                )}
                                {statusMeta && (
                                    <StatusBadge
                                        tone={statusMeta.tone}
                                        variant="soft"
                                        size="sm"
                                    >
                                        {statusMeta.label}
                                    </StatusBadge>
                                )}
                                {duration && (
                                    <span
                                        className="ml-1 rounded bg-surface-raised px-1.5 py-0.5 font-mono text-[0.7rem] tabular-nums text-muted-foreground"
                                        data-testid="header-duration"
                                    >
                                        {duration}
                                    </span>
                                )}
                            </div>
                            <div className="text-caption text-muted-foreground truncate font-mono">
                                {incident.id.slice(0, 8)} · {incident.typ} ·{" "}
                                {incident.ort || "–"}
                            </div>
                        </button>
                    </>
                ) : (
                    <div className="flex items-center gap-2 text-muted-foreground">
                        <span className="block h-2.5 w-2.5 rounded-full bg-status-gray" />
                        <span className="text-body">
                            Kein Incident aktiv – bitte starten oder auswaehlen
                        </span>
                        {onGoToIncidents && (
                            <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={onGoToIncidents}
                                data-testid="header-no-incident-cta"
                            >
                                <LayoutGrid className="h-3.5 w-3.5" />
                                Uebersicht
                            </Button>
                        )}
                    </div>
                )}
            </div>

            {/* Rolle */}
            {(() => {
                const RoleIcon = roleMeta ? ROLE_ICON[roleMeta.key] : UserCog;
                return (
                    <button
                        type="button"
                        onClick={() => setPickerOpen(true)}
                        data-testid="header-role-button"
                        title="Rolle wechseln"
                        className="hidden sm:flex items-center gap-1.5 rounded-md bg-surface-raised px-2.5 h-8 text-caption els-focus-ring hover:border-primary/60 border border-border transition-colors"
                    >
                        <RoleIcon className="h-3.5 w-3.5 text-primary" />
                        <span className="text-muted-foreground">Rolle:</span>
                        <span className="font-medium" data-testid="header-role">
                            {roleMeta ? roleMeta.label : "waehlen"}
                        </span>
                        {roleMeta && (
                            <span className="rounded bg-background px-1.5 py-0.5 font-mono text-[0.65rem] text-muted-foreground">
                                {roleMeta.kurz}
                            </span>
                        )}
                    </button>
                );
            })()}

            {/* Command Palette Trigger */}
            <CommandPaletteTrigger />

            {/* Uhrzeit */}
            <div
                className="hidden md:flex items-center gap-2 rounded-md bg-surface-raised px-2.5 py-1"
                data-testid="header-clock"
            >
                <Clock3 className="h-3.5 w-3.5 text-muted-foreground" />
                <div className="leading-tight text-right">
                    <div className="text-body font-mono tabular-nums">
                        {formatTime(now)}
                    </div>
                    <div className="text-[0.7rem] text-muted-foreground font-mono">
                        {formatDate(now)}
                    </div>
                </div>
            </div>

            {/* Theme-Toggle */}
            <Button
                type="button"
                variant="outline"
                size="icon"
                onClick={onToggleTheme}
                aria-label="Theme wechseln"
                data-testid="theme-toggle"
                className="h-8 w-8"
            >
                {theme === "light" ? (
                    <Moon className="h-4 w-4" />
                ) : (
                    <Sun className="h-4 w-4" />
                )}
            </Button>
        </header>
    );
}
