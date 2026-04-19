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
import { ROLES, ROLE_KEYS, useRole } from "@/context/RoleContext";
import { ShieldCheck, Stethoscope, FileCheck2 } from "lucide-react";

const ROLE_ICON = {
    einsatzleiter: ShieldCheck,
    helfer: Stethoscope,
    dokumentar: FileCheck2
};

export function RoleSelectorDialog() {
    const { role, setRole, pickerOpen, setPickerOpen } = useRole();

    const handleSelect = (key) => {
        setRole(key);
        setPickerOpen(false);
    };

    return (
        <Dialog
            open={pickerOpen}
            onOpenChange={(v) => {
                if (!v && !role) return; // nicht schliessbar wenn noch nichts gewaehlt
                setPickerOpen(v);
            }}
        >
            <DialogContent
                className="sm:max-w-lg bg-card border-border"
                data-testid="role-selector"
            >
                <DialogHeader>
                    <DialogTitle className="text-heading">
                        Rolle auswaehlen
                    </DialogTitle>
                    <DialogDescription className="text-body text-muted-foreground">
                        Die gewaehlte Rolle bestimmt Navigation, Sichtbarkeiten und
                        Bearbeitungsrechte. Wechsel jederzeit via Header oder Kommando-Palette.
                    </DialogDescription>
                </DialogHeader>

                <div className="grid grid-cols-1 gap-2">
                    {ROLE_KEYS.map((k) => {
                        const meta = ROLES[k];
                        const Icon = ROLE_ICON[k];
                        const active = role === k;
                        return (
                            <button
                                key={k}
                                type="button"
                                onClick={() => handleSelect(k)}
                                data-testid={`role-opt-${k}`}
                                className={cn(
                                    "els-surface flex items-start gap-3 p-3 text-left transition-colors els-focus-ring",
                                    active && "border-primary/60 bg-primary/10",
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
                                                AKTIV
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

                {role && (
                    <DialogFooter>
                        <Button
                            variant="outline"
                            onClick={() => setPickerOpen(false)}
                            data-testid="role-selector-close"
                        >
                            Schliessen
                        </Button>
                    </DialogFooter>
                )}
            </DialogContent>
        </Dialog>
    );
}
