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
import { cn } from "@/lib/utils";
import { ROLES, ROLE_KEYS, useRole } from "@/context/RoleContext";
import { ShieldCheck, Stethoscope, FileCheck2, Radio, Layers, UserCheck } from "lucide-react";
import { toast } from "sonner";

const ROLE_ICON = {
    einsatzleiter: ShieldCheck,
    fuehrungsassistenz: Radio,
    abschnittleitung: Layers,
    helfer: Stethoscope,
    dokumentar: FileCheck2
};

/**
 * Rollen-Picker mit Pflicht-Identifikation: Vor- und Nachname werden zusammen
 * mit der gewaehlten Rolle gespeichert. Beide Felder sind Pflicht (>=2 Zeichen)
 * damit jeder Funktagebuch-Eintrag und jede FMS-Quittierung nachvollziehbar
 * dokumentiert ist.
 */
export function RoleSelectorDialog() {
    const { role, userName, setIdentity, pickerOpen, setPickerOpen } = useRole();
    const [selectedRole, setSelectedRole] = React.useState(role || "");
    const [firstName, setFirstName] = React.useState("");
    const [lastName, setLastName] = React.useState("");

    // Beim Oeffnen: bestehende Werte vorbefuellen (Vor-/Nachname rekonstruieren).
    React.useEffect(() => {
        if (!pickerOpen) return;
        setSelectedRole(role || "");
        if (userName) {
            const parts = userName.trim().split(/\s+/);
            if (parts.length >= 2) {
                setFirstName(parts.slice(0, -1).join(" "));
                setLastName(parts[parts.length - 1]);
            } else {
                setFirstName(userName);
                setLastName("");
            }
        } else {
            setFirstName("");
            setLastName("");
        }
    }, [pickerOpen, role, userName]);

    const firstOk = firstName.trim().length >= 2;
    const lastOk = lastName.trim().length >= 2;
    const formValid = Boolean(selectedRole) && firstOk && lastOk;

    const handleConfirm = () => {
        if (!formValid) {
            if (!selectedRole) toast.error("Bitte eine Rolle waehlen.");
            else if (!firstOk) toast.error("Vorname ist Pflicht (mind. 2 Zeichen).");
            else if (!lastOk) toast.error("Nachname ist Pflicht (mind. 2 Zeichen).");
            return;
        }
        const fullName = `${firstName.trim()} ${lastName.trim()}`;
        setIdentity(selectedRole, fullName);
        setPickerOpen(false);
        toast.success(`Angemeldet als ${fullName} (${ROLES[selectedRole]?.kurz || selectedRole})`);
    };

    const handleKeyDown = (e) => {
        if (e.key === "Enter" && formValid) {
            e.preventDefault();
            handleConfirm();
        }
    };

    return (
        <Dialog
            open={pickerOpen}
            onOpenChange={(v) => {
                // Erst schliessbar wenn Rolle + Name gesetzt
                if (!v && (!role || !userName)) return;
                setPickerOpen(v);
            }}
        >
            <DialogContent
                className="sm:max-w-lg bg-card border-border max-h-[90vh] overflow-y-auto"
                data-testid="role-selector"
            >
                <DialogHeader>
                    <DialogTitle className="text-heading">
                        Anmeldung
                    </DialogTitle>
                    <DialogDescription className="text-body text-muted-foreground">
                        Vor- und Nachname sowie Rolle sind Pflicht. Diese Identifikation
                        wird zur Dokumentation und Nachvollziehbarkeit fuer Funktagebuch-
                        Eintraege und FMS-Quittierungen genutzt.
                    </DialogDescription>
                </DialogHeader>

                {/* Identitaet */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                        <Label htmlFor="role-firstname">
                            Vorname<span className="text-status-red ml-0.5">*</span>
                        </Label>
                        <Input
                            id="role-firstname"
                            value={firstName}
                            onChange={(e) => setFirstName(e.target.value)}
                            onKeyDown={handleKeyDown}
                            placeholder="z.B. Max"
                            autoFocus
                            maxLength={40}
                            data-testid="role-firstname"
                            aria-invalid={!firstOk}
                        />
                    </div>
                    <div className="space-y-1.5">
                        <Label htmlFor="role-lastname">
                            Nachname<span className="text-status-red ml-0.5">*</span>
                        </Label>
                        <Input
                            id="role-lastname"
                            value={lastName}
                            onChange={(e) => setLastName(e.target.value)}
                            onKeyDown={handleKeyDown}
                            placeholder="z.B. Mustermann"
                            maxLength={60}
                            data-testid="role-lastname"
                            aria-invalid={!lastOk}
                        />
                    </div>
                </div>

                {/* Rolle */}
                <div className="space-y-1.5">
                    <Label>
                        Rolle<span className="text-status-red ml-0.5">*</span>
                    </Label>
                    <div className="grid grid-cols-1 gap-2">
                        {ROLE_KEYS.map((k) => {
                            const meta = ROLES[k];
                            const Icon = ROLE_ICON[k];
                            const active = selectedRole === k;
                            return (
                                <button
                                    key={k}
                                    type="button"
                                    onClick={() => setSelectedRole(k)}
                                    data-testid={`role-opt-${k}`}
                                    className={cn(
                                        "els-surface flex items-start gap-3 p-3 text-left transition-colors els-focus-ring",
                                        active && "border-primary/80 bg-primary/15 ring-1 ring-primary/30",
                                        !active && "hover:border-primary/60 hover:bg-surface-raised"
                                    )}
                                >
                                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-primary/15 text-primary">
                                        <Icon className="h-5 w-5" />
                                    </div>
                                    <div className="min-w-0 flex-1">
                                        <div className="flex items-center gap-2">
                                            <span className="text-heading">{meta.label}</span>
                                            <span className="rounded bg-surface-raised px-1.5 py-0.5 font-mono text-[0.65rem] text-muted-foreground">
                                                {meta.kurz}
                                            </span>
                                            {active && (
                                                <span className="rounded bg-primary px-1.5 py-0.5 text-[0.65rem] text-primary-foreground">
                                                    GEWAEHLT
                                                </span>
                                            )}
                                        </div>
                                        <p className="mt-0.5 text-caption text-muted-foreground">
                                            {meta.beschreibung}
                                        </p>
                                    </div>
                                </button>
                            );
                        })}
                    </div>
                </div>

                <DialogFooter className="flex-row items-center justify-between gap-2">
                    <div className="text-caption text-muted-foreground">
                        {formValid ? (
                            <span className="inline-flex items-center gap-1">
                                <UserCheck className="h-3.5 w-3.5 text-status-green" />
                                Bereit
                            </span>
                        ) : (
                            <span className="text-status-red/80">
                                Vorname, Nachname und Rolle erforderlich
                            </span>
                        )}
                    </div>
                    <div className="flex gap-2">
                        {role && userName && (
                            <Button
                                variant="outline"
                                onClick={() => setPickerOpen(false)}
                                data-testid="role-selector-close"
                            >
                                Abbrechen
                            </Button>
                        )}
                        <Button
                            onClick={handleConfirm}
                            disabled={!formValid}
                            data-testid="role-selector-confirm"
                        >
                            Anmelden
                        </Button>
                    </div>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
