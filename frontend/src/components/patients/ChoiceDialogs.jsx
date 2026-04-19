import * as React from "react";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
    TRANSPORT_TYP,
    FALLABSCHLUSS_TYP
} from "@/lib/patient-meta";

const TRANSPORT_OPTIONS = [
    { key: "intern", ...TRANSPORT_TYP.intern },
    { key: "extern", ...TRANSPORT_TYP.extern }
];
const ABSCHLUSS_OPTIONS = [
    { key: "rd_uebergabe", ...FALLABSCHLUSS_TYP.rd_uebergabe },
    { key: "entlassung", ...FALLABSCHLUSS_TYP.entlassung },
    { key: "manuell", ...FALLABSCHLUSS_TYP.manuell }
];

function ToneClass(tone) {
    return {
        red: "border-status-red/40 hover:bg-status-red/10 data-[active=true]:bg-status-red data-[active=true]:text-status-red-fg",
        yellow:
            "border-status-yellow/40 hover:bg-status-yellow/10 data-[active=true]:bg-status-yellow data-[active=true]:text-status-yellow-fg",
        green:
            "border-status-green/40 hover:bg-status-green/10 data-[active=true]:bg-status-green data-[active=true]:text-status-green-fg",
        gray:
            "border-status-gray/40 hover:bg-status-gray/10 data-[active=true]:bg-status-gray data-[active=true]:text-status-gray-fg",
        info:
            "border-primary/40 hover:bg-primary/10 data-[active=true]:bg-primary data-[active=true]:text-primary-foreground"
    }[tone];
}

/**
 * Generischer Auswahl-Dialog fuer Transport / Fallabschluss.
 */
export function ChoiceDialog({
    open,
    onOpenChange,
    title,
    description,
    options = [],
    onSelect,
    testId = "choice-dialog"
}) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                className="sm:max-w-lg bg-card border-border"
                data-testid={testId}
            >
                <DialogHeader>
                    <DialogTitle className="text-heading">{title}</DialogTitle>
                    {description && (
                        <DialogDescription className="text-body text-muted-foreground">
                            {description}
                        </DialogDescription>
                    )}
                </DialogHeader>

                <div className="grid grid-cols-1 gap-2">
                    {options.map((o) => (
                        <button
                            key={o.key}
                            type="button"
                            onClick={() => {
                                onSelect(o.key);
                                onOpenChange?.(false);
                            }}
                            data-testid={`${testId}-opt-${o.key}`}
                            className={cn(
                                "els-surface flex items-start gap-3 border p-3 text-left transition-colors els-focus-ring",
                                ToneClass(o.tone)
                            )}
                        >
                            <div className="flex-1 min-w-0">
                                <div className="text-heading">{o.label}</div>
                                <div className="text-caption text-muted-foreground group-hover:text-inherit">
                                    {o.description}
                                </div>
                            </div>
                        </button>
                    ))}
                </div>

                <DialogFooter>
                    <Button
                        type="button"
                        variant="outline"
                        onClick={() => onOpenChange?.(false)}
                        data-testid={`${testId}-cancel`}
                    >
                        Abbrechen
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

export function TransportChoiceDialog({ open, onOpenChange, onSelect }) {
    return (
        <ChoiceDialog
            open={open}
            onOpenChange={onOpenChange}
            title="Transport anfordern"
            description="Typ der Ressource fuer den Transport waehlen."
            options={TRANSPORT_OPTIONS}
            onSelect={onSelect}
            testId="transport-dialog"
        />
    );
}

export function FallabschlussChoiceDialog({ open, onOpenChange, onSelect }) {
    return (
        <ChoiceDialog
            open={open}
            onOpenChange={onOpenChange}
            title="Fallabschluss"
            description="Art des Abschlusses bestimmt Verbleib und Zeitstempel."
            options={ABSCHLUSS_OPTIONS}
            onSelect={onSelect}
            testId="fallabschluss-dialog"
        />
    );
}
