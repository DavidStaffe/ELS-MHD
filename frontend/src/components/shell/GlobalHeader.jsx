import * as React from "react";
import { cn } from "@/lib/utils";
import { StatusBadge } from "@/components/primitives/StatusBadge";
import { Button } from "@/components/ui/button";
import { CommandPaletteTrigger } from "@/components/command/CommandPalette";
import { Sun, Moon, ShieldCheck, Clock3 } from "lucide-react";

function useClock() {
    const [now, setNow] = React.useState(() => new Date());
    React.useEffect(() => {
        const id = setInterval(() => setNow(new Date()), 1000);
        return () => clearInterval(id);
    }, []);
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

/**
 * GlobalHeader – Incident-Kontext, Rolle, Uhrzeit, Theme-Toggle.
 * Laut Spec: Zeigt aktiven Incident, Rolle, Abschlussstatus.
 */
export function GlobalHeader({
    incident,
    role = "Einsatzleiter",
    theme,
    onToggleTheme,
    className
}) {
    const now = useClock();

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
                            <span className="block h-2.5 w-2.5 rounded-full bg-status-green" />
                            <span
                                aria-hidden
                                className="absolute inset-0 rounded-full bg-status-green animate-pulse-ring"
                            />
                        </div>
                        <div className="min-w-0">
                            <div className="flex items-center gap-2">
                                <span className="text-heading truncate">
                                    {incident.name}
                                </span>
                                {incident.demo && (
                                    <StatusBadge
                                        tone="yellow"
                                        variant="solid"
                                        size="sm"
                                        data-testid="incident-demo-badge"
                                    >
                                        DEMO
                                    </StatusBadge>
                                )}
                                <StatusBadge tone="green" variant="soft" size="sm">
                                    {incident.status ?? "Operativ"}
                                </StatusBadge>
                            </div>
                            <div className="text-caption text-muted-foreground truncate font-mono">
                                {incident.id} · {incident.type} · {incident.location}
                            </div>
                        </div>
                    </>
                ) : (
                    <div className="flex items-center gap-2 text-muted-foreground">
                        <span className="block h-2.5 w-2.5 rounded-full bg-status-gray" />
                        <span className="text-body">
                            Kein Incident aktiv – bitte starten oder auswaehlen
                        </span>
                    </div>
                )}
            </div>

            {/* Rolle */}
            <div className="hidden sm:flex items-center gap-1.5 rounded-md bg-surface-raised px-2.5 py-1 text-caption">
                <ShieldCheck className="h-3.5 w-3.5 text-primary" />
                <span className="text-muted-foreground">Rolle:</span>
                <span className="font-medium" data-testid="header-role">
                    {role}
                </span>
            </div>

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
