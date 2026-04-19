import * as React from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { SICHTUNG } from "@/lib/patient-meta";
import { Plus, Keyboard } from "lucide-react";

/**
 * QuickEntryBar – Schnellerfassung am unteren Bildschirmrand.
 * 2-Tap-Flow: [Sichtung waehlen] -> Patient sofort mit Sichtung+Status=in_behandlung angelegt.
 * Zusaetzlich: "+" Button oeffnet den ausfuehrlicheren Dialog.
 *
 * Tastaturkuerzel: 1 = S1, 2 = S2, 3 = S3, 4 = S4, N = Neu (Dialog).
 */
export function QuickEntryBar({
    onQuickCreate,
    onOpenDialog,
    disabled = false,
    className
}) {
    const [busyKey, setBusyKey] = React.useState(null);

    const handleQuick = React.useCallback(
        async (level) => {
            if (busyKey || disabled) return;
            setBusyKey(level);
            try {
                await onQuickCreate?.({ sichtung: level });
            } finally {
                setBusyKey(null);
            }
        },
        [busyKey, disabled, onQuickCreate]
    );

    React.useEffect(() => {
        const handler = (e) => {
            if (disabled) return;
            // Nicht auslösen in Eingabefeldern
            const target = e.target;
            const tag = target?.tagName?.toLowerCase();
            const isEditable =
                tag === "input" ||
                tag === "textarea" ||
                tag === "select" ||
                target?.isContentEditable;
            if (isEditable) return;
            // Modifier ignorieren
            if (e.metaKey || e.ctrlKey || e.altKey) return;

            const k = e.key.toLowerCase();
            const match = SICHTUNG.find((s) => s.shortcut === k);
            if (match) {
                e.preventDefault();
                handleQuick(match.key);
                return;
            }
            if (k === "n") {
                e.preventDefault();
                onOpenDialog?.();
            }
        };
        window.addEventListener("keydown", handler);
        return () => window.removeEventListener("keydown", handler);
    }, [disabled, handleQuick, onOpenDialog]);

    const toneClass = {
        red: "bg-status-red text-status-red-fg hover:bg-status-red/90",
        yellow: "bg-status-yellow text-status-yellow-fg hover:bg-status-yellow/90",
        green: "bg-status-green text-status-green-fg hover:bg-status-green/90",
        gray: "bg-status-gray text-status-gray-fg hover:bg-status-gray/90"
    };

    return (
        <div
            data-testid="quick-entry-bar"
            className={cn(
                "sticky bottom-0 z-20 flex items-center gap-3 border-t border-border bg-surface-sunken/95 px-4 py-3 backdrop-blur",
                className
            )}
        >
            <div className="flex items-center gap-2 text-caption text-muted-foreground">
                <Keyboard className="h-3.5 w-3.5" />
                <span className="font-medium text-foreground">
                    Schnellerfassung
                </span>
                <span className="hidden md:inline">
                    · Tippe eine Sichtung fuer sofortige Anlage
                </span>
            </div>

            <div className="ml-auto flex items-center gap-2">
                {SICHTUNG.map((s) => (
                    <button
                        key={s.key}
                        type="button"
                        disabled={disabled || busyKey !== null}
                        onClick={() => handleQuick(s.key)}
                        data-testid={`quick-sichtung-${s.key}`}
                        title={`${s.label} – ${s.hint} (Taste ${s.shortcut})`}
                        className={cn(
                            "relative inline-flex h-12 w-16 flex-col items-center justify-center rounded-md font-semibold shadow-sm transition-all active:scale-[0.97] disabled:opacity-60",
                            "els-focus-ring",
                            toneClass[s.tone]
                        )}
                    >
                        <span className="font-mono text-display leading-none">
                            {s.key}
                        </span>
                        <span className="text-[0.65rem] uppercase opacity-80">
                            {s.hint.split(" ")[0]}
                        </span>
                        <kbd className="absolute -top-1.5 -right-1.5 inline-flex h-4 w-4 items-center justify-center rounded-sm border border-border bg-background text-[0.6rem] font-mono text-foreground">
                            {s.shortcut}
                        </kbd>
                        {busyKey === s.key && (
                            <span className="absolute inset-0 rounded-md bg-black/20 animate-pulse" />
                        )}
                    </button>
                ))}

                <div className="mx-1 h-10 w-px bg-border" />

                <Button
                    onClick={onOpenDialog}
                    disabled={disabled}
                    data-testid="quick-open-dialog"
                    variant="outline"
                    className="h-12"
                >
                    <Plus className="h-4 w-4" />
                    <span className="hidden sm:inline">Detail-Erfassung</span>
                    <kbd className="ml-1 hidden sm:inline-flex h-4 w-4 items-center justify-center rounded-sm border border-border bg-background text-[0.6rem] font-mono">
                        N
                    </kbd>
                </Button>
            </div>
        </div>
    );
}
