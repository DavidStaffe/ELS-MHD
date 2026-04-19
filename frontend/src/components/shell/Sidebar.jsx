import * as React from "react";
import { NavLink, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";
import { useIncidents } from "@/context/IncidentContext";
import {
    LayoutGrid,
    Activity,
    Users,
    Truck,
    Boxes,
    Radio,
    AlertOctagon,
    FileCheck2,
    Settings,
    Layers,
    Bed,
    Archive
} from "lucide-react";

/**
 * Sidebar – Modul-Navigation ELS MHD.
 * - Einstieg (Incident-Uebersicht) + Archiv immer verfuegbar.
 * - Lage + Module nur verfuegbar wenn aktiver Incident existiert.
 * - Bei archiviertem Incident: operative Module gesperrt (Lese-Modus).
 */
const NAV_GROUPS = (hasIncident, isArchived) => [
    {
        label: "Start",
        items: [
            {
                to: "/",
                icon: LayoutGrid,
                label: "Einstieg",
                testId: "nav-einstieg",
                end: true
            },
            {
                to: "/archiv",
                icon: Archive,
                label: "Archiv",
                testId: "nav-archiv"
            }
        ]
    },
    {
        label: isArchived ? "Archivierter Incident" : "Aktiver Incident",
        items: [
            {
                to: "/lage",
                icon: Activity,
                label: "Lage",
                testId: "nav-lage",
                disabled: !hasIncident,
                hint: hasIncident ? (isArchived ? "lesen" : null) : "inaktiv"
            },
            {
                to: "/patienten",
                icon: Users,
                label: "Patienten",
                testId: "nav-patienten",
                disabled: !hasIncident || isArchived,
                hint: !hasIncident ? "inaktiv" : isArchived ? "gesperrt" : null
            },
            {
                to: "/transport",
                icon: Truck,
                label: "Transport",
                testId: "nav-transport",
                disabled: !hasIncident || isArchived,
                hint: !hasIncident ? "inaktiv" : isArchived ? "gesperrt" : null
            },
            {
                to: "/ressourcen",
                icon: Boxes,
                label: "Ressourcen",
                testId: "nav-ressourcen",
                disabled: !hasIncident || isArchived,
                hint: !hasIncident ? "inaktiv" : isArchived ? "gesperrt" : null
            },
            {
                to: "/abschnitte",
                icon: Layers,
                label: "Abschnitte",
                testId: "nav-abschnitte",
                disabled: !hasIncident || isArchived,
                hint: !hasIncident ? "inaktiv" : isArchived ? "gesperrt" : null
            },
            {
                to: "/betten",
                icon: Bed,
                label: "Behandlungsplaetze",
                testId: "nav-betten",
                disabled: !hasIncident || isArchived,
                hint: !hasIncident ? "inaktiv" : isArchived ? "gesperrt" : null
            },
            {
                to: "/kommunikation",
                icon: Radio,
                label: "Funktagebuch",
                testId: "nav-kommunikation",
                disabled: !hasIncident || isArchived,
                hint: !hasIncident ? "inaktiv" : isArchived ? "gesperrt" : null
            },
            {
                to: "/konflikte",
                icon: AlertOctagon,
                label: "Konflikte",
                testId: "nav-konflikte",
                disabled: !hasIncident || isArchived,
                hint: !hasIncident ? "inaktiv" : isArchived ? "gesperrt" : null
            }
        ]
    },
    {
        label: "Abschluss",
        items: [
            {
                to: "/abschluss",
                icon: FileCheck2,
                label: "Auswertung",
                testId: "nav-abschluss",
                disabled: !hasIncident,
                hint: hasIncident ? (isArchived ? "lesen" : null) : "inaktiv"
            }
        ]
    }
];

export function Sidebar({ className }) {
    const { activeIncident } = useIncidents();
    const hasIncident = Boolean(activeIncident);
    const isArchived = activeIncident?.status === "abgeschlossen";
    const groups = NAV_GROUPS(hasIncident, isArchived);

    return (
        <aside
            data-testid="app-sidebar"
            className={cn(
                "flex h-screen w-sidebar shrink-0 flex-col border-r border-border bg-surface-sunken",
                className
            )}
        >
            {/* Logo / Marke */}
            <div className="flex h-header items-center gap-2.5 border-b border-border px-4">
                <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground shadow-sm">
                    <span className="font-mono text-heading font-bold">E</span>
                </div>
                <div className="min-w-0">
                    <div className="text-heading leading-tight">ELS MHD</div>
                    <div className="text-caption text-muted-foreground leading-tight">
                        Einsatzleitsystem
                    </div>
                </div>
            </div>

            <nav className="flex-1 overflow-y-auto py-4">
                {groups.map((group) => (
                    <div key={group.label} className="mb-4 px-3">
                        <div className="mb-1.5 px-2 text-[0.7rem] uppercase tracking-wider text-muted-foreground">
                            {group.label}
                        </div>
                        <ul className="space-y-0.5">
                            {group.items.map((item) => {
                                const Icon = item.icon;
                                if (item.disabled) {
                                    return (
                                        <li key={item.to}>
                                            <div
                                                aria-disabled
                                                data-testid={item.testId}
                                                className="flex items-center gap-2.5 rounded-md px-2 py-1.5 text-body text-muted-foreground/60"
                                            >
                                                <Icon className="h-4 w-4" />
                                                <span className="flex-1 truncate">
                                                    {item.label}
                                                </span>
                                                {item.hint && (
                                                    <span className="text-[0.65rem] uppercase tracking-wider text-muted-foreground/60">
                                                        {item.hint}
                                                    </span>
                                                )}
                                                {item.step && (
                                                    <span className="font-mono text-[0.65rem] text-muted-foreground/60">
                                                        {item.step}
                                                    </span>
                                                )}
                                            </div>
                                        </li>
                                    );
                                }
                                return (
                                    <li key={item.to}>
                                        <NavLink
                                            to={item.to}
                                            end={item.end}
                                            data-testid={item.testId}
                                            className={({ isActive }) =>
                                                cn(
                                                    "flex items-center gap-2.5 rounded-md px-2 py-1.5 text-body transition-colors els-focus-ring",
                                                    isActive
                                                        ? "bg-primary/15 text-primary"
                                                        : "text-foreground/85 hover:bg-surface-raised hover:text-foreground"
                                                )
                                            }
                                        >
                                            <Icon className="h-4 w-4" />
                                            <span className="truncate">
                                                {item.label}
                                            </span>
                                        </NavLink>
                                    </li>
                                );
                            })}
                        </ul>
                    </div>
                ))}
            </nav>

            <div className="border-t border-border px-3 py-3">
                <div className="flex items-center gap-2.5 rounded-md px-2 py-1.5 text-body text-muted-foreground/70">
                    <Settings className="h-4 w-4" />
                    <span className="flex-1 truncate">Einstellungen</span>
                    <span className="font-mono text-[0.65rem]">v0.2</span>
                </div>
            </div>
        </aside>
    );
}
