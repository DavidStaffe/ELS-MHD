import * as React from "react";
import { useNavigate } from "react-router-dom";
import { useIncidents } from "@/context/IncidentContext";
import { Button } from "@/components/ui/button";
import { SectionCard, StatusBadge } from "@/components/primitives";
import { ArrowLeft, Users, Truck, Boxes, Radio, AlertOctagon, FileCheck2 } from "lucide-react";

/**
 * LagePlatzhalter – Zwischenseite nach Incident-Auswahl.
 * Die eigentlichen Module (Patienten, Transport, Ressourcen, Kommunikation,
 * Konflikte, Auswertung) folgen in Schritten 03–09.
 */
export default function LagePlaceholder() {
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

    const modules = [
        { step: "03", label: "Patienten", icon: Users, description: "Erfassung, Sichtung, Status, Verbleib" },
        { step: "05", label: "Transport", icon: Truck, description: "Intern / extern, Zuteilung, Zeitstempel" },
        { step: "06", label: "Ressourcen", icon: Boxes, description: "Fahrzeuge, Personal, Material" },
        { step: "06", label: "Kommunikation", icon: Radio, description: "Meldungen, Quittierung" },
        { step: "06", label: "Konflikte", icon: AlertOctagon, description: "Blocker & Warnungen" },
        { step: "09", label: "Auswertung & Abschluss", icon: FileCheck2, description: "14-Kapitel-Bericht, PDF" }
    ];

    return (
        <div className="mx-auto w-full max-w-[1200px] px-6 py-6">
            <div className="mb-6 flex items-center justify-between gap-4">
                <div>
                    <div className="text-caption uppercase tracking-wider text-muted-foreground">
                        Lagebild · {activeIncident.demo && "DEMO · "}
                        {activeIncident.typ}
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
                    onClick={() => navigate("/")}
                    data-testid="lage-back"
                >
                    <ArrowLeft className="h-4 w-4" />
                    Uebersicht
                </Button>
            </div>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                {modules.map((m) => {
                    const Icon = m.icon;
                    return (
                        <SectionCard
                            key={`${m.step}-${m.label}`}
                            title={
                                <span className="flex items-center gap-2">
                                    <Icon className="h-4 w-4 text-primary" />
                                    {m.label}
                                </span>
                            }
                            subtitle={m.description}
                            action={
                                <StatusBadge tone="gray" size="sm">
                                    Schritt {m.step}
                                </StatusBadge>
                            }
                        >
                            <p className="text-caption text-muted-foreground">
                                Das Modul folgt in einem der naechsten
                                Implementierungsschritte.
                            </p>
                        </SectionCard>
                    );
                })}
            </div>
        </div>
    );
}
