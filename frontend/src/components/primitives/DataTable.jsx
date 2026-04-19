import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * DataTable – leichte Tabelle fuer Leitstellen-Listen.
 * columns: [{ key, label, align?, width?, render?, mono? }]
 * rows: Array<Record<string, any>>
 * onRowClick: (row) => void
 */
export function DataTable({
    columns = [],
    rows = [],
    onRowClick,
    rowKey = "id",
    empty = "Keine Eintraege.",
    dense = false,
    className,
    testId,
    ...props
}) {
    const rowPad = dense ? "py-1.5" : "py-2.5";
    return (
        <div
            className={cn(
                "els-surface overflow-hidden",
                className
            )}
            data-testid={testId ?? "data-table"}
            {...props}
        >
            <div className="overflow-x-auto">
                <table className="w-full border-collapse text-body">
                    <thead className="bg-surface-sunken">
                        <tr>
                            {columns.map((c) => (
                                <th
                                    key={c.key}
                                    scope="col"
                                    style={{ width: c.width }}
                                    className={cn(
                                        "text-caption font-medium uppercase tracking-wider text-muted-foreground border-b border-border px-3 py-2 text-left",
                                        c.align === "right" && "text-right",
                                        c.align === "center" && "text-center"
                                    )}
                                >
                                    {c.label}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {rows.length === 0 && (
                            <tr>
                                <td
                                    colSpan={columns.length}
                                    className="px-3 py-8 text-center text-caption text-muted-foreground"
                                >
                                    {empty}
                                </td>
                            </tr>
                        )}
                        {rows.map((r, i) => (
                            <tr
                                key={r[rowKey] ?? i}
                                onClick={
                                    onRowClick ? () => onRowClick(r) : undefined
                                }
                                data-testid="data-table-row"
                                className={cn(
                                    "border-b border-border last:border-0 transition-colors",
                                    onRowClick &&
                                        "cursor-pointer hover:bg-surface-raised"
                                )}
                            >
                                {columns.map((c) => (
                                    <td
                                        key={c.key}
                                        className={cn(
                                            "px-3 align-middle",
                                            rowPad,
                                            c.align === "right" && "text-right",
                                            c.align === "center" && "text-center",
                                            c.mono && "font-mono"
                                        )}
                                    >
                                        {c.render
                                            ? c.render(r)
                                            : r[c.key] ?? "–"}
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
