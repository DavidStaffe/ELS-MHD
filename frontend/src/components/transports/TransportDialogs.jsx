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
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
    resourcesForTyp,
    TRANSPORT_ZIEL,
    ZIEL_OPTIONS,
    occupiedResources
} from "@/lib/transport-meta";
import { Truck } from "lucide-react";

/**
 * ResourceAssignDialog – Ressource fuer Transport waehlen.
 */
export function ResourceAssignDialog({
    open,
    onOpenChange,
    transport,
    transports = [],
    onAssign
}) {
    if (!transport) return null;
    const options = resourcesForTyp(transport.typ);
    const occ = occupiedResources(transports);

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                className="sm:max-w-lg bg-card border-border"
                data-testid="resource-assign-dialog"
            >
                <DialogHeader>
                    <DialogTitle className="text-heading">
                        Ressource zuweisen
                    </DialogTitle>
                    <DialogDescription className="text-body text-muted-foreground">
                        {transport.patient_kennung ? (
                            <>
                                Patient <span className="font-mono font-medium">{transport.patient_kennung}</span>{" "}
                                · Typ {transport.typ === "intern" ? "Intern" : "Extern"}
                            </>
                        ) : (
                            <>Typ {transport.typ === "intern" ? "Intern" : "Extern"}</>
                        )}
                    </DialogDescription>
                </DialogHeader>

                <div className="grid grid-cols-2 gap-2">
                    {options.map((r) => {
                        const busy = occ.get(r.name) || [];
                        const isBusy =
                            busy.length > 0 && busy[0].id !== transport.id;
                        return (
                            <button
                                key={r.id}
                                type="button"
                                onClick={() => {
                                    onAssign(r.name);
                                    onOpenChange?.(false);
                                }}
                                data-testid={`resource-assign-opt-${r.id}`}
                                className={cn(
                                    "flex items-center gap-2 rounded-md border px-3 py-2 text-left els-focus-ring",
                                    isBusy
                                        ? "border-status-yellow/60 bg-status-yellow/10"
                                        : "border-border hover:border-primary/60 hover:bg-surface-raised"
                                )}
                            >
                                <Truck className="h-4 w-4 text-primary" />
                                <div className="min-w-0 flex-1">
                                    <div className="font-medium truncate">
                                        {r.name}
                                    </div>
                                    {isBusy && (
                                        <div className="text-[0.65rem] text-status-yellow">
                                            aktuell belegt · {busy.length}
                                        </div>
                                    )}
                                </div>
                            </button>
                        );
                    })}
                </div>

                <DialogFooter>
                    <Button
                        type="button"
                        variant="outline"
                        onClick={() => onOpenChange?.(false)}
                        data-testid="resource-assign-cancel"
                    >
                        Abbrechen
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

/**
 * NewTransportDialog – Transport ohne Patient manuell anlegen.
 */
export function NewTransportDialog({ open, onOpenChange, onCreate }) {
    const [typ, setTyp] = React.useState("extern");
    const [ziel, setZiel] = React.useState("krankenhaus");
    const [ressource, setRessource] = React.useState("");
    const [submitting, setSubmitting] = React.useState(false);
    const [error, setError] = React.useState(null);

    React.useEffect(() => {
        if (!open) return;
        setTyp("extern");
        setZiel("krankenhaus");
        setRessource("");
        setError(null);
    }, [open]);

    const options = resourcesForTyp(typ);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSubmitting(true);
        setError(null);
        try {
            await onCreate({
                typ,
                ziel,
                ressource: ressource || null
            });
            onOpenChange?.(false);
        } catch (err) {
            setError(err?.response?.data?.detail || err?.message || "Fehler");
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                className="sm:max-w-lg bg-card border-border"
                data-testid="new-transport-dialog"
            >
                <DialogHeader>
                    <DialogTitle className="text-heading">
                        Transport manuell anlegen
                    </DialogTitle>
                    <DialogDescription className="text-body text-muted-foreground">
                        Nutze dies fuer Transporte ohne zugeordneten Patienten
                        (z.B. Materialfahrten). Patient-Transporte entstehen
                        automatisch beim Setzen von transport_typ.
                    </DialogDescription>
                </DialogHeader>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-1.5">
                            <Label htmlFor="nt-typ">Typ</Label>
                            <Select value={typ} onValueChange={setTyp}>
                                <SelectTrigger id="nt-typ" data-testid="nt-typ">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="intern">Intern</SelectItem>
                                    <SelectItem value="extern">Extern</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="space-y-1.5">
                            <Label htmlFor="nt-ziel">Ziel</Label>
                            <Select value={ziel} onValueChange={setZiel}>
                                <SelectTrigger id="nt-ziel" data-testid="nt-ziel">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {ZIEL_OPTIONS.map((z) => (
                                        <SelectItem key={z} value={z}>
                                            {TRANSPORT_ZIEL[z].label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    </div>

                    <div className="space-y-1.5">
                        <Label htmlFor="nt-res">Ressource (optional)</Label>
                        <Select
                            value={ressource || "__none__"}
                            onValueChange={(v) =>
                                setRessource(v === "__none__" ? "" : v)
                            }
                        >
                            <SelectTrigger id="nt-res" data-testid="nt-res">
                                <SelectValue placeholder="Spaeter zuweisen" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="__none__">
                                    — keine Ressource (offen) —
                                </SelectItem>
                                {options.map((r) => (
                                    <SelectItem key={r.id} value={r.name}>
                                        {r.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {error && (
                        <div className="rounded-md border border-status-red/40 bg-status-red/10 px-3 py-2 text-caption text-status-red">
                            {error}
                        </div>
                    )}

                    <DialogFooter className="gap-2">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => onOpenChange?.(false)}
                            disabled={submitting}
                            data-testid="nt-cancel"
                        >
                            Abbrechen
                        </Button>
                        <Button type="submit" disabled={submitting} data-testid="nt-submit">
                            {submitting ? "Speichern…" : "Anlegen"}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}
