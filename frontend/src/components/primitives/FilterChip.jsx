import * as React from "react";
import { cn } from "@/lib/utils";
import { X } from "lucide-react";

/**
 * FilterChip – toggelbar, optional mit Count, optional loeschbar.
 */
export const FilterChip = React.forwardRef(function FilterChip(
    {
        active = false,
        onToggle,
        onRemove,
        count,
        tone = "neutral",
        className,
        children,
        ...props
    },
    ref
) {
    const toneActive = {
        neutral: "bg-primary text-primary-foreground border-primary",
        red: "bg-status-red text-status-red-fg border-status-red",
        yellow: "bg-status-yellow text-status-yellow-fg border-status-yellow",
        green: "bg-status-green text-status-green-fg border-status-green",
        gray: "bg-status-gray text-status-gray-fg border-status-gray"
    }[tone] ?? "bg-primary text-primary-foreground border-primary";

    return (
        <button
            ref={ref}
            type="button"
            role="checkbox"
            aria-checked={active}
            onClick={onToggle}
            data-testid="filter-chip"
            data-active={active}
            className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-3 h-7 text-caption font-medium transition-colors els-focus-ring",
                active
                    ? toneActive
                    : "bg-transparent text-foreground border-border hover:bg-muted",
                className
            )}
            {...props}
        >
            <span>{children}</span>
            {typeof count === "number" && (
                <span
                    className={cn(
                        "rounded-full px-1.5 min-w-[1.25rem] text-center font-mono text-[0.7rem] leading-4",
                        active
                            ? "bg-black/15"
                            : "bg-muted text-muted-foreground"
                    )}
                >
                    {count}
                </span>
            )}
            {onRemove && (
                <span
                    role="button"
                    tabIndex={-1}
                    onClick={(e) => {
                        e.stopPropagation();
                        onRemove();
                    }}
                    className="ml-0.5 rounded-full p-0.5 hover:bg-black/15"
                    data-testid="filter-chip-remove"
                >
                    <X className="h-3 w-3" />
                </span>
            )}
        </button>
    );
});
