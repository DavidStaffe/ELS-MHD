import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * StatusBadge – farbkodierter Status nach ELS-Spec.
 * tone: red | yellow | green | gray | info | neutral
 * variant: solid (gefuellt) | soft (transparent) | outline
 */
const toneStyles = {
    red: {
        solid: "bg-status-red text-status-red-fg",
        soft: "bg-status-red/15 text-status-red border border-status-red/30",
        outline: "text-status-red border border-status-red/60"
    },
    yellow: {
        solid: "bg-status-yellow text-status-yellow-fg",
        soft: "bg-status-yellow/15 text-status-yellow border border-status-yellow/30",
        outline: "text-status-yellow border border-status-yellow/60"
    },
    green: {
        solid: "bg-status-green text-status-green-fg",
        soft: "bg-status-green/15 text-status-green border border-status-green/30",
        outline: "text-status-green border border-status-green/60"
    },
    gray: {
        solid: "bg-status-gray text-status-gray-fg",
        soft: "bg-status-gray/15 text-foreground border border-status-gray/30",
        outline: "text-foreground border border-status-gray/50"
    },
    info: {
        solid: "bg-status-info text-status-info-fg",
        soft: "bg-status-info/15 text-status-info border border-status-info/30",
        outline: "text-status-info border border-status-info/60"
    },
    neutral: {
        solid: "bg-muted text-foreground",
        soft: "bg-muted/60 text-foreground border border-border",
        outline: "text-foreground border border-border"
    }
};

/**
 * Sichtungsstufen-Badge (S1–S4).
 */
export const SichtungToneMap = {
    S1: "red",
    S2: "yellow",
    S3: "green",
    S4: "gray"
};

export const StatusBadge = React.forwardRef(function StatusBadge(
    {
        tone = "neutral",
        variant = "soft",
        size = "md",
        dot = false,
        className,
        children,
        ...props
    },
    ref
) {
    const sizeCls =
        size === "sm"
            ? "text-[0.7rem] px-1.5 py-0.5 h-5"
            : size === "lg"
                ? "text-body px-3 py-1 h-7"
                : "text-caption px-2 py-0.5 h-6";

    return (
        <span
            ref={ref}
            data-testid={`status-badge-${tone}`}
            className={cn(
                "inline-flex items-center gap-1.5 rounded-md font-medium uppercase tracking-wide whitespace-nowrap",
                sizeCls,
                toneStyles[tone]?.[variant] ?? toneStyles.neutral.soft,
                className
            )}
            {...props}
        >
            {dot && (
                <span
                    aria-hidden
                    className={cn(
                        "inline-block rounded-full",
                        size === "sm" ? "h-1.5 w-1.5" : "h-2 w-2",
                        tone === "red" && "bg-status-red",
                        tone === "yellow" && "bg-status-yellow",
                        tone === "green" && "bg-status-green",
                        tone === "gray" && "bg-status-gray",
                        tone === "info" && "bg-status-info",
                        tone === "neutral" && "bg-muted-foreground"
                    )}
                />
            )}
            {children}
        </span>
    );
});

/**
 * Sichtungs-Badge fuer S1–S4 (farbkodiert laut Spec).
 */
export function SichtungBadge({ level, size = "md", className, ...props }) {
    const tone = SichtungToneMap[level] ?? "neutral";
    return (
        <StatusBadge
            tone={tone}
            variant="solid"
            size={size}
            className={cn("font-mono tracking-tighter", className)}
            data-testid={`sichtung-badge-${level}`}
            {...props}
        >
            {level}
        </StatusBadge>
    );
}
