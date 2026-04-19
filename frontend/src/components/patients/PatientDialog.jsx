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
import { Textarea } from "@/components/ui/textarea";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import {
    SICHTUNG,
    STATUS_OPTIONS,
    VERBLEIB_OPTIONS,
    PATIENT_STATUS,
    PATIENT_VERBLEIB
} from "@/lib/patient-meta";

export function PatientDialog({
    open,
    onOpenChange,
    initial = null,
    onSubmit
}) {
    const isEdit = !!initial;
    const [sichtung, setSichtung] = React.useState(initial?.sichtung ?? "");
    const [status, setStatus] = React.useState(initial?.status ?? "wartend");
    const [verbleib, setVerbleib] = React.useState(initial?.verbleib ?? "unbekannt");
    const [notiz, setNotiz] = React.useState(initial?.notiz ?? "");
    const [submitting, setSubmitting] = React.useState(false);
    const [error, setError] = React.useState(null);

    React.useEffect(() => {
        if (!open) return;
        setSichtung(initial?.sichtung ?? "");
        setStatus(initial?.status ?? "wartend");
        setVerbleib(initial?.verbleib ?? "unbekannt");
        setNotiz(initial?.notiz ?? "");
        setError(null);
    }, [open, initial]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSubmitting(true);
        setError(null);
        try {
            const payload = {
                status,
                verbleib,
                notiz: notiz.trim()
            };
            if (sichtung) payload.sichtung = sichtung;
            await onSubmit(payload);
            onOpenChange?.(false);
        } catch (err) {
            setError(
                err?.response?.data?.detail || err?.message || "Fehler beim Speichern"
            );
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                className="sm:max-w-lg bg-card border-border"
                data-testid="patient-dialog"
            >
                <DialogHeader>
                    <DialogTitle className="text-heading">
                        {isEdit
                            ? `Patient bearbeiten (${initial.kennung})`
                            : "Neuen Patienten anlegen"}
                    </DialogTitle>
                    <DialogDescription className="text-body text-muted-foreground">
                        {isEdit
                            ? "Aenderungen werden protokolliert; Zeitstempel werden automatisch gesetzt."
                            : "Die Kennung wird automatisch vergeben. Sichtung kann auch spaeter gesetzt werden."}
                    </DialogDescription>
                </DialogHeader>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="space-y-2">
                        <Label>Sichtungsstufe</Label>
                        <div className="grid grid-cols-4 gap-2">
                            {SICHTUNG.map((s) => {
                                const active = sichtung === s.key;
                                return (
                                    <button
                                        key={s.key}
                                        type="button"
                                        onClick={() =>
                                            setSichtung(active ? "" : s.key)
                                        }
                                        data-testid={`pd-sichtung-${s.key}`}
                                        className={cn(
                                            "flex flex-col items-center justify-center rounded-md border py-3 font-semibold transition-colors",
                                            active
                                                ? s.tone === "red"
                                                    ? "bg-status-red text-status-red-fg border-status-red"
                                                    : s.tone === "yellow"
                                                        ? "bg-status-yellow text-status-yellow-fg border-status-yellow"
                                                        : s.tone === "green"
                                                            ? "bg-status-green text-status-green-fg border-status-green"
                                                            : "bg-status-gray text-status-gray-fg border-status-gray"
                                                : "border-border text-foreground hover:bg-surface-raised"
                                        )}
                                    >
                                        <span className="font-mono text-heading">
                                            {s.key}
                                        </span>
                                        <span className="text-[0.65rem] uppercase tracking-wider opacity-80">
                                            {s.hint.split(" ")[0]}
                                        </span>
                                    </button>
                                );
                            })}
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-1.5">
                            <Label htmlFor="pd-status">Status</Label>
                            <Select value={status} onValueChange={setStatus}>
                                <SelectTrigger id="pd-status" data-testid="pd-status">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {STATUS_OPTIONS.map((s) => (
                                        <SelectItem key={s} value={s}>
                                            {PATIENT_STATUS[s].label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="space-y-1.5">
                            <Label htmlFor="pd-verbleib">Verbleib</Label>
                            <Select value={verbleib} onValueChange={setVerbleib}>
                                <SelectTrigger
                                    id="pd-verbleib"
                                    data-testid="pd-verbleib"
                                >
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {VERBLEIB_OPTIONS.map((s) => (
                                        <SelectItem key={s} value={s}>
                                            {PATIENT_VERBLEIB[s]}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    </div>

                    <div className="space-y-1.5">
                        <Label htmlFor="pd-notiz">Notiz</Label>
                        <Textarea
                            id="pd-notiz"
                            data-testid="pd-notiz"
                            value={notiz}
                            onChange={(e) => setNotiz(e.target.value)}
                            rows={3}
                            maxLength={4000}
                            placeholder="z.B. Schnittwunde Unterarm, kreislaufstabil"
                        />
                    </div>

                    {error && (
                        <div
                            className="rounded-md border border-status-red/40 bg-status-red/10 px-3 py-2 text-caption text-status-red"
                            data-testid="pd-error"
                        >
                            {error}
                        </div>
                    )}

                    <DialogFooter className="gap-2">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => onOpenChange?.(false)}
                            disabled={submitting}
                            data-testid="pd-cancel"
                        >
                            Abbrechen
                        </Button>
                        <Button
                            type="submit"
                            disabled={submitting}
                            data-testid="pd-submit"
                        >
                            {submitting ? "Speichern…" : isEdit ? "Speichern" : "Anlegen"}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}
