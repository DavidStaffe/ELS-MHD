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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AlertTriangle, Trash2 } from "lucide-react";

const CONFIRM_WORD = "LÖSCHEN";

/**
 * DeleteArchivModal – geschuetzter Loesch-Dialog fuer archivierte Incidents.
 * Bestaetigung erfolgt NUR durch Texteingabe des Wortes "LÖSCHEN".
 */
export function DeleteArchivModal({ open, onOpenChange, incident, onConfirm }) {
    const [text, setText] = React.useState("");
    const [busy, setBusy] = React.useState(false);

    React.useEffect(() => {
        if (!open) {
            setText("");
            setBusy(false);
        }
    }, [open]);

    const ok = text === CONFIRM_WORD;

    const handleConfirm = async () => {
        if (!ok || busy) return;
        setBusy(true);
        try {
            await onConfirm?.();
            onOpenChange?.(false);
        } finally {
            setBusy(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                className="sm:max-w-md bg-card border-border"
                data-testid="archiv-delete-modal"
            >
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2 text-heading text-status-red">
                        <AlertTriangle className="h-4 w-4" />
                        Archivierten Incident endgueltig loeschen?
                    </DialogTitle>
                    <DialogDescription className="text-body text-muted-foreground">
                        {incident ? (
                            <>
                                <span className="font-medium text-foreground">
                                    "{incident.name}"
                                </span>{" "}
                                wird unwiderruflich entfernt – inklusive aller Patienten,
                                Transporte, Ressourcen, Meldungen, Abschnitte, Betten und
                                Bericht-Versionen. Diese Aktion kann nicht rueckgaengig
                                gemacht werden.
                            </>
                        ) : null}
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-2 py-1">
                    <Label htmlFor="archiv-delete-input" className="text-caption">
                        Zur Bestaetigung tippe{" "}
                        <code className="font-mono rounded bg-surface-raised px-1.5 py-0.5 text-status-red">
                            {CONFIRM_WORD}
                        </code>{" "}
                        in das Feld:
                    </Label>
                    <Input
                        id="archiv-delete-input"
                        autoFocus
                        value={text}
                        onChange={(e) => setText(e.target.value)}
                        placeholder={CONFIRM_WORD}
                        className="font-mono bg-background"
                        data-testid="archiv-delete-input"
                        onKeyDown={(e) => {
                            if (e.key === "Enter" && ok) handleConfirm();
                        }}
                    />
                </div>

                <DialogFooter className="gap-2">
                    <Button
                        variant="outline"
                        onClick={() => onOpenChange?.(false)}
                        data-testid="archiv-delete-cancel"
                    >
                        Abbrechen
                    </Button>
                    <Button
                        variant="destructive"
                        disabled={!ok || busy}
                        onClick={handleConfirm}
                        data-testid="archiv-delete-confirm"
                    >
                        <Trash2 className="h-3.5 w-3.5" />
                        {busy ? "Loesche…" : "Endgueltig loeschen"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
