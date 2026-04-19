import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * SectionCard – Basis-Karte mit Titel, Aktion, optionalem Footer.
 * Fuer dichte Leitstellen-Layouts (kompakter als shadcn Card).
 */
export const SectionCard = React.forwardRef(function SectionCard(
    {
        title,
        subtitle,
        action,
        footer,
        padded = true,
        className,
        bodyClassName,
        children,
        testId,
        ...props
    },
    ref
) {
    return (
        <section
            ref={ref}
            data-testid={testId ?? "section-card"}
            className={cn("els-surface flex flex-col", className)}
            {...props}
        >
            {(title || action) && (
                <header className="flex items-start justify-between gap-3 border-b border-border px-4 py-3">
                    <div className="min-w-0">
                        {title && (
                            <h3 className="text-heading truncate">{title}</h3>
                        )}
                        {subtitle && (
                            <p className="mt-0.5 text-caption text-muted-foreground truncate">
                                {subtitle}
                            </p>
                        )}
                    </div>
                    {action && <div className="shrink-0">{action}</div>}
                </header>
            )}
            <div className={cn(padded && "p-4", "flex-1", bodyClassName)}>
                {children}
            </div>
            {footer && (
                <footer className="border-t border-border px-4 py-2.5 text-caption text-muted-foreground">
                    {footer}
                </footer>
            )}
        </section>
    );
});
