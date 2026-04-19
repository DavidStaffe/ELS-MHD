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
import { AlertTriangle } from "lucide-react";

/**
 * ConfirmModal – Bestaetigungsdialog mit optionaler Warnung (Ampel).
 * tone: "default" | "destructive" | "warning"
 */
export function ConfirmModal({
    open,
    onOpenChange,
    title,
    description,
    confirmLabel = "Bestaetigen",
    cancelLabel = "Abbrechen",
    onConfirm,
    tone = "default",
    children,
    testId = "confirm-modal"
}) {
    const headerIconColor = {
        destructive: "text-status-red",
        warning: "text-status-yellow",
        default: "text-primary"
    }[tone];

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                className="sm:max-w-md bg-card border-border"
                data-testid={testId}
            >
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2 text-heading">
                        {tone !== "default" && (
                            <AlertTriangle
                                className={cn("h-4 w-4", headerIconColor)}
                            />
                        )}
                        {title}
                    </DialogTitle>
                    {description && (
                        <DialogDescription className="text-body text-muted-foreground">
                            {description}
                        </DialogDescription>
                    )}
                </DialogHeader>
                {children && <div className="py-2">{children}</div>}
                <DialogFooter className="gap-2">
                    <Button
                        variant="outline"
                        onClick={() => onOpenChange?.(false)}
                        data-testid={`${testId}-cancel`}
                    >
                        {cancelLabel}
                    </Button>
                    <Button
                        variant={tone === "destructive" ? "destructive" : "default"}
                        onClick={() => {
                            onConfirm?.();
                            onOpenChange?.(false);
                        }}
                        data-testid={`${testId}-confirm`}
                    >
                        {confirmLabel}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
