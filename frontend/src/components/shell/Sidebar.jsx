import * as React from "react";
import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";
import {
    LayoutDashboard,
    Users,
    Truck,
    Boxes,
    Radio,
    AlertOctagon,
    FileCheck2,
    Settings
} from "lucide-react";

/**
 * Sidebar – Modul-Navigation ELS MHD.
 * Laut Handlungsablauf: Patient, Transport, Ressourcen, Kommunikation, Konflikte, Abschluss.
 */
const NAV_GROUPS = [
    {
        label: "Lage",
        items: [
            { to: "/", icon: LayoutDashboard, label: "Einstieg", testId: "nav-einstieg" }
        ]
    },
    {
        label: "Operativ",
        items: [
            { to: "/patienten", icon: Users, label: "Patienten", testId: "nav-patienten", disabled: true, step: "02/03" },
            { to: "/transport", icon: Truck, label: "Transport", testId: "nav-transport", disabled: true, step: "05" },
            { to: "/ressourcen", icon: Boxes, label: "Ressourcen", testId: "nav-ressourcen", disabled: true, step: "06" },
            { to: "/kommunikation", icon: Radio, label: "Kommunikation", testId: "nav-kommunikation", disabled: true, step: "06" },
            { to: "/konflikte", icon: AlertOctagon, label: "Konflikte", testId: "nav-konflikte", disabled: true, step: "06" }
        ]
    },
    {
        label: "Abschluss",
        items: [
            { to: "/abschluss", icon: FileCheck2, label: "Auswertung", testId: "nav-abschluss", disabled: true, step: "09" }
        ]
    }
];

export function Sidebar({ className }) {
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
                {NAV_GROUPS.map((group) => (
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
                                                className="flex items-center gap-2.5 rounded-md px-2 py-1.5 text-body text-muted-foreground/70"
                                            >
                                                <Icon className="h-4 w-4" />
                                                <span className="flex-1 truncate">
                                                    {item.label}
                                                </span>
                                                <span className="font-mono text-[0.65rem] text-muted-foreground/60">
                                                    {item.step}
                                                </span>
                                            </div>
                                        </li>
                                    );
                                }
                                return (
                                    <li key={item.to}>
                                        <NavLink
                                            to={item.to}
                                            end
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
                    <span className="font-mono text-[0.65rem]">v0.1</span>
                </div>
            </div>
        </aside>
    );
}
