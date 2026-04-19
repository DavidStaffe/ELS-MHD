import * as React from "react";
import { useNavigate } from "react-router-dom";
import { useIncidents } from "@/context/IncidentContext";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/primitives";
import { Dashboard } from "@/components/lage/Dashboard";
import { cn } from "@/lib/utils";
import {
    ArrowLeft,
    Users,
    Truck,
    Boxes,
    Radio,
    AlertOctagon,
    FileCheck2,
    Layers,
    Bed,
    Lock
} from "lucide-react";

/**
 * LagePage – schnelle Lage-Uebersicht (Dashboard) + Modul-Schnellzugriff.
 * Ersetzt den bisherigen LagePlatzhalter. Das Dashboard wurde aus
 * "Auswertung & Abschluss" hierher verschoben.
 *
 * Fuer abgeschlossene Incidents: Dashboard bleibt lesbar, Modul-Kacheln
 * sind deaktiviert (Archiv-Modus).
 */
export default function LagePage() {
    const { activeIncident } = useIncidents();
    const navigate = useNavigate();

    if (!activeIncident) {
        return (
            <div className="mx-auto max-w-2xl p-6">
                <div className="els-surface p-6 text-center" data-testid="lage-no-incident">
                    <h2 className="text-display">Kein Incident aktiv</h2>
                    <p className="mt-2 text-muted-foreground">
                        Waehle zunaechst einen Incident aus der Uebersicht.
                    </p>
                    <Button
                        className="mt-4"
                        onClick={() => navigate("/")}
                        data-testid="lage-back"
                    >
                        <ArrowLeft className="h-4 w-4" />
                        Zur Incident-Uebersicht
                    </Button>
                </div>
            </div>
        );
    }

    const isArchived = activeIncident.status === "abgeschlossen";

    const modules = [
        { label: "Patienten", icon: Users, description: "Erfassung, Sichtung, Status, Verbleib", to: "/patienten" },
        { label: "Transport", icon: Truck, description: "Intern / extern, Zuteilung, Zeitstempel", to: "/transport" },
        { label: "Ressourcen", icon: Boxes, description: "Fahrzeuge, Personal, Material", to: "/ressourcen" },
        { label: "Abschnitte", icon: Layers, description: "Einsatzabschnitte, Farbcode", to: "/abschnitte" },
        { label: "Behandlungsplaetze", icon: Bed, description: "UHS-Betten, Belegung, Zuweisung", to: "/betten" },
        { label: "Funktagebuch", icon: Radio, description: "Meldungen, Quittierung, Finalisierung", to: "/kommunikation" },
        { label: "Konflikte", icon: AlertOctagon, description: "Blocker & Warnungen", to: "/konflikte" },
        { label: "Auswertung & Abschluss", icon: FileCheck2, description: "Check, Bericht, Versionen", to: "/abschluss" }
    ];

    return (
        <div className="mx-auto w-full max-w-[1400px] px-6 py-6 space-y-6">
            {/* Kopf */}
            <div className="flex flex-wrap items-end justify-between gap-4">
                <div>
                    <div className="text-caption uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                        Lagebild · {activeIncident.demo && "DEMO · "}
                        {activeIncident.typ}
                        {isArchived && (
                            <StatusBadge tone="gray" variant="soft" size="sm">
                                <Lock className="h-3 w-3" />
                                archiviert · nur Lesen
                            </StatusBadge>
                        )}
                    </div>
                    <h1 className="mt-1 text-display" data-testid="lage-title">
                        {activeIncident.name}
                    </h1>
                    <p className="mt-1 text-body text-muted-foreground">
                        {activeIncident.ort || "Kein Ort hinterlegt"}
                    </p>
                </div>
                <Button
                    variant="outline"
                    onClick={() => navigate(isArchived ? "/archiv" : "/")}
                    data-testid="lage-back"
                >
                    <ArrowLeft className="h-4 w-4" />
                    {isArchived ? "Zum Archiv" : "Uebersicht"}
                </Button>
            </div>

            {/* Dashboard (schnelle Lage-Uebersicht) */}
            <Dashboard />

            {/* Modul-Schnellzugriff */}
            <div>
                <div className="mb-3 text-caption uppercase tracking-wider text-muted-foreground">
                    Module · Schnellzugriff
                </div>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
                    {modules.map((m) => {
                        const Icon = m.icon;
                        // Im Archiv-Modus: nur Auswertung (Lesen) aktiv
                        const disabled = isArchived && m.to !== "/abschluss";
                        const Wrapper = disabled ? "div" : "button";
                        return (
                            <Wrapper
                                key={m.label}
                                type={disabled ? undefined : "button"}
                                onClick={disabled ? undefined : () => navigate(m.to)}
                                data-testid={`lage-module-${m.label.toLowerCase().replace(/[^a-z]/g, "")}`}
                                aria-disabled={disabled || undefined}
                                className={cn(
                                    "els-surface text-left flex items-start gap-3 p-4 transition-all",
                                    disabled
                                        ? "opacity-50 cursor-not-allowed"
                                        : "hover:border-primary/60 hover:bg-surface-raised els-focus-ring cursor-pointer"
                                )}
                            >
                                <Icon className="h-5 w-5 mt-0.5 text-primary shrink-0" />
                                <div className="min-w-0 flex-1">
                                    <div className="text-heading">{m.label}</div>
                                    <p className="mt-0.5 text-caption text-muted-foreground">
                                        {m.description}
                                    </p>
                                </div>
                                {disabled && (
                                    <Lock className="h-3.5 w-3.5 text-muted-foreground shrink-0 mt-1" />
                                )}
                            </Wrapper>
                        );
                    })}
                </div>
            </div>
        </div>
    );
}
