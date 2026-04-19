import * as React from "react";
import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

/**
 * KpiTile – kompakte Kennzahlen-Kachel.
 * Props: label, value, unit, trend ("up"|"down"|"flat"|null), trendValue, tone, hint
 */
export const KpiTile = React.forwardRef(function KpiTile(
    {
        label,
        value,
        unit,
        trend = null,
        trendValue,
        tone = "default",
        hint,
        onClick,
        className,
        testId,
        ...props
    },
    ref
) {
    const toneBar = {
        default: "bg-primary/80",
        red: "bg-status-red",
        yellow: "bg-status-yellow",
        green: "bg-status-green",
        gray: "bg-status-gray"
    }[tone] ?? "bg-primary/80";

    const TrendIcon =
        trend === "up" ? TrendingUp : trend === "down" ? TrendingDown : Minus;
    const trendColor =
        trend === "up"
            ? "text-status-green"
            : trend === "down"
                ? "text-status-red"
                : "text-muted-foreground";

    const Wrapper = onClick ? "button" : "div";

    return (
        <Wrapper
            ref={ref}
            onClick={onClick}
            data-testid={testId ?? "kpi-tile"}
            className={cn(
                "els-surface relative overflow-hidden p-4 text-left transition-colors",
                onClick &&
                    "hover:border-primary/60 hover:bg-surface-raised els-focus-ring cursor-pointer",
                className
            )}
            {...props}
        >
            <span
                aria-hidden
                className={cn("absolute left-0 top-0 h-full w-0.5", toneBar)}
            />
            <div className="flex items-center justify-between gap-2">
                <span className="text-caption uppercase tracking-wider text-muted-foreground">
                    {label}
                </span>
                {trend && (
                    <span
                        className={cn(
                            "inline-flex items-center gap-1 text-caption",
                            trendColor
                        )}
                    >
                        <TrendIcon className="h-3 w-3" />
                        {trendValue}
                    </span>
                )}
            </div>
            <div className="mt-2 flex items-baseline gap-1.5">
                <span className="text-kpi tabular-nums">{value}</span>
                {unit && (
                    <span className="text-caption text-muted-foreground">
                        {unit}
                    </span>
                )}
            </div>
            {hint && (
                <div className="mt-1 text-caption text-muted-foreground">
                    {hint}
                </div>
            )}
        </Wrapper>
    );
});
