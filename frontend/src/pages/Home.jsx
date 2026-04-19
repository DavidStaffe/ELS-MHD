import * as React from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    StatusBadge,
    SichtungBadge,
    KpiTile,
    FilterChip,
    SectionCard,
    DataTable,
    ConfirmModal
} from "@/components/primitives";
import { useCommandPalette } from "@/components/command/CommandPalette";
import {
    Users,
    Truck,
    Boxes,
    Radio,
    PlayCircle,
    Plus,
    FileCheck2,
    Info,
    Command as CommandIcon
} from "lucide-react";

/**
 * Home – Produktbasis-Uebersicht.
 * Zeigt in EINEM Screen alle Designsystem-Bausteine im operativen Kontext.
 * Produktionsnah, keine Showcase-Gimmicks.
 * Dient gleichzeitig als Einstieg fuer Schritt 02 (Incident-Auswahl).
 */

const DEMO_PATIENTS = [
    { id: "P-0013", sichtung: "S1", status: "In Behandlung", verbleib: "UHS", dauer: "00:06" },
    { id: "P-0014", sichtung: "S2", status: "Wartend", verbleib: "–", dauer: "00:11" },
    { id: "P-0015", sichtung: "S3", status: "Transportbereit", verbleib: "RD", dauer: "00:22" },
    { id: "P-0016", sichtung: "S4", status: "Entlassen", verbleib: "Event", dauer: "00:03" }
];

const COLUMNS = [
    { key: "id", label: "Kennung", mono: true, width: "22%" },
    {
        key: "sichtung",
        label: "Sichtung",
        width: "18%",
        render: (r) => <SichtungBadge level={r.sichtung} />
    },
    {
        key: "status",
        label: "Status",
        render: (r) => {
            const tone =
                r.status === "In Behandlung"
                    ? "info"
                    : r.status === "Wartend"
                        ? "yellow"
                        : r.status === "Transportbereit"
                            ? "green"
                            : "gray";
            return (
                <StatusBadge tone={tone} variant="soft" dot size="sm">
                    {r.status}
                </StatusBadge>
            );
        }
    },
    { key: "verbleib", label: "Verbleib", width: "14%" },
    { key: "dauer", label: "Dauer", mono: true, align: "right", width: "12%" }
];

export default function Home({ demoOpen, setDemoOpen, newOpen, setNewOpen }) {
    const [filter, setFilter] = React.useState({ S1: true, S2: true, S3: false, S4: false, offen: true });
    // Fallback-State falls Home ohne App-Shell-Handler genutzt wird
    const [localDemo, setLocalDemo] = React.useState(false);
    const [localNew, setLocalNew] = React.useState(false);
    const isDemoOpen = demoOpen ?? localDemo;
    const setIsDemoOpen = setDemoOpen ?? setLocalDemo;
    const isNewOpen = newOpen ?? localNew;
    const setIsNewOpen = setNewOpen ?? setLocalNew;

    const { registerCommand } = useCommandPalette();

    // Demo-Registrierung dynamischer Commands (zeigt API-Muster fuer spaetere Schritte)
    React.useEffect(() => {
        const unregisters = [];
        unregisters.push(
            registerCommand({
                id: "focus-patient-search",
                label: "Patient nach Kennung suchen",
                group: "Schnellzugriff",
                icon: Users,
                keywords: ["kennung", "pat", "p-"],
                run: () => {
                    const el = document.querySelector('[data-testid="patient-search"]');
                    if (el) el.focus();
                }
            })
        );
        unregisters.push(
            registerCommand({
                id: "scroll-kpi",
                label: "Kennzahlen anzeigen",
                group: "Schnellzugriff",
                icon: FileCheck2,
                keywords: ["kpi", "zahlen", "lage"],
                run: () => window.scrollTo({ top: 0, behavior: "smooth" })
            })
        );
        return () => unregisters.forEach((u) => u && u());
    }, [registerCommand]);

    return (
        <div className="mx-auto w-full max-w-[1600px] px-6 py-6">
            {/* Kopfzeile */}
            <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
                <div>
                    <div className="text-caption uppercase tracking-wider text-muted-foreground">
                        Schritt 01 · Produktbasis
                    </div>
                    <h1 className="mt-1 text-display" data-testid="home-title">
                        Willkommen im ELS MHD
                    </h1>
                    <p className="mt-1 max-w-2xl text-body text-muted-foreground">
                        Sanitaetsdienstliches Einsatzleitsystem fuer Grossveranstaltungen.
                        Waehle einen bestehenden Incident oder starte einen neuen. Fuer Tests
                        kann ein Demo-Incident mit Vordaten geladen werden.
                    </p>
                </div>
                <div className="flex flex-wrap gap-2">
                    <Button
                        variant="outline"
                        data-testid="btn-start-demo"
                        onClick={() => setIsDemoOpen(true)}
                    >
                        <PlayCircle className="h-4 w-4" />
                        Demo-Incident starten
                    </Button>
                    <Button
                        data-testid="btn-new-incident"
                        onClick={() => setIsNewOpen(true)}
                    >
                        <Plus className="h-4 w-4" />
                        Neuen Incident anlegen
                    </Button>
                </div>
            </div>

            {/* KPI-Zeile – Live-Kennzahlen-Vorschau */}
            <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
                <KpiTile
                    label="Patienten aktiv"
                    value="24"
                    unit="Pat."
                    tone="default"
                    hint="4 neu in 5 Min."
                    testId="kpi-patienten"
                />
                <KpiTile
                    label="S1 kritisch"
                    value="3"
                    tone="red"
                    trend="up"
                    trendValue="+1"
                    testId="kpi-s1"
                />
                <KpiTile
                    label="Transporte offen"
                    value="5"
                    unit="offen"
                    tone="yellow"
                    hint="2 intern · 3 extern"
                    testId="kpi-transporte"
                />
                <KpiTile
                    label="Ressourcen verfuegbar"
                    value="12/18"
                    tone="green"
                    trend="flat"
                    trendValue="0"
                    testId="kpi-ressourcen"
                />
                <KpiTile
                    label="Konflikte"
                    value="1"
                    tone="red"
                    hint="1 Blocker offen"
                    testId="kpi-konflikte"
                />
                <KpiTile
                    label="Einsatzdauer"
                    value="02:14"
                    unit="h"
                    tone="gray"
                    hint="seit 14:03"
                    testId="kpi-dauer"
                />
            </div>

            {/* Zwei-Spalten-Layout (Spec-gemaess 60/40) */}
            <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1.6fr_1fr]">
                {/* Patienten-Vorschau */}
                <SectionCard
                    title="Patienten (Vorschau)"
                    subtitle="Schritt 03 baut die vollstaendige Liste. Hier nur Designsystem-Referenz."
                    padded={false}
                    action={
                        <Button variant="ghost" size="sm" disabled>
                            Alle anzeigen
                        </Button>
                    }
                    testId="section-patienten"
                >
                    <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-3">
                        <span className="text-caption text-muted-foreground">
                            Sichtung:
                        </span>
                        <FilterChip
                            tone="red"
                            active={filter.S1}
                            onToggle={() =>
                                setFilter((f) => ({ ...f, S1: !f.S1 }))
                            }
                            count={3}
                        >
                            S1
                        </FilterChip>
                        <FilterChip
                            tone="yellow"
                            active={filter.S2}
                            onToggle={() =>
                                setFilter((f) => ({ ...f, S2: !f.S2 }))
                            }
                            count={8}
                        >
                            S2
                        </FilterChip>
                        <FilterChip
                            tone="green"
                            active={filter.S3}
                            onToggle={() =>
                                setFilter((f) => ({ ...f, S3: !f.S3 }))
                            }
                            count={9}
                        >
                            S3
                        </FilterChip>
                        <FilterChip
                            tone="gray"
                            active={filter.S4}
                            onToggle={() =>
                                setFilter((f) => ({ ...f, S4: !f.S4 }))
                            }
                            count={4}
                        >
                            S4
                        </FilterChip>
                        <span className="mx-2 h-4 w-px bg-border" />
                        <FilterChip
                            active={filter.offen}
                            onToggle={() =>
                                setFilter((f) => ({ ...f, offen: !f.offen }))
                            }
                        >
                            Nur offene
                        </FilterChip>
                        <div className="ml-auto">
                            <Input
                                type="search"
                                placeholder="Kennung suchen…"
                                className="h-8 w-48 bg-background"
                                data-testid="patient-search"
                            />
                        </div>
                    </div>
                    <DataTable
                        columns={COLUMNS}
                        rows={DEMO_PATIENTS}
                        testId="table-patienten"
                        dense
                    />
                </SectionCard>

                {/* Rechte Spalte – Designsystem-Referenz */}
                <div className="flex flex-col gap-5">
                    <SectionCard
                        title="Status-Badges"
                        subtitle="Sichtungsstufen (S1–S4) + operativer Status"
                        testId="section-badges"
                    >
                        <div className="mb-3">
                            <div className="text-caption mb-2 text-muted-foreground">
                                Sichtung
                            </div>
                            <div className="flex flex-wrap gap-2">
                                <SichtungBadge level="S1" />
                                <SichtungBadge level="S2" />
                                <SichtungBadge level="S3" />
                                <SichtungBadge level="S4" />
                            </div>
                        </div>
                        <div>
                            <div className="text-caption mb-2 text-muted-foreground">
                                Operativer Status
                            </div>
                            <div className="flex flex-wrap gap-2">
                                <StatusBadge tone="info" dot>
                                    In Behandlung
                                </StatusBadge>
                                <StatusBadge tone="yellow" dot>
                                    Wartend
                                </StatusBadge>
                                <StatusBadge tone="green" dot>
                                    Transportbereit
                                </StatusBadge>
                                <StatusBadge tone="gray" dot>
                                    Entlassen
                                </StatusBadge>
                                <StatusBadge tone="red" variant="solid">
                                    Blocker
                                </StatusBadge>
                                <StatusBadge tone="yellow" variant="outline">
                                    Warnung
                                </StatusBadge>
                            </div>
                        </div>
                    </SectionCard>

                    <SectionCard
                        title="Buttons & Aktionen"
                        subtitle="Primaer / Sekundaer / Destruktiv"
                        testId="section-buttons"
                    >
                        <div className="flex flex-wrap gap-2">
                            <Button>
                                <FileCheck2 className="h-4 w-4" />
                                Freigeben
                            </Button>
                            <Button variant="secondary">Entwurf speichern</Button>
                            <Button variant="outline">Abbrechen</Button>
                            <Button variant="destructive">Blocker loesen</Button>
                            <Button variant="ghost">Mehr</Button>
                        </div>
                    </SectionCard>

                    <SectionCard
                        title="Naechste Schritte"
                        subtitle="Module werden in Schritt 02–09 implementiert"
                        testId="section-roadmap"
                    >
                        <ul className="space-y-2 text-body">
                            {[
                                { step: "02", label: "Einstieg & Incident-Auswahl", icon: PlayCircle },
                                { step: "03", label: "Patientenliste", icon: Users },
                                { step: "04", label: "Patientendetail", icon: Users },
                                { step: "05", label: "Transportuebersicht", icon: Truck },
                                { step: "06", label: "Ressourcen / Komm. / Konflikte", icon: Boxes },
                                { step: "07", label: "Produktreife", icon: Radio },
                                { step: "08", label: "Demo-Integration", icon: PlayCircle },
                                { step: "09", label: "Auswertung & Abschluss", icon: FileCheck2 }
                            ].map((s) => {
                                const Icon = s.icon;
                                return (
                                    <li
                                        key={s.step}
                                        className="flex items-center gap-3"
                                    >
                                        <span className="inline-flex h-6 w-8 shrink-0 items-center justify-center rounded-sm bg-surface-raised font-mono text-caption">
                                            {s.step}
                                        </span>
                                        <Icon className="h-4 w-4 text-muted-foreground" />
                                        <span className="flex-1 truncate">
                                            {s.label}
                                        </span>
                                        <StatusBadge tone="gray" size="sm">
                                            offen
                                        </StatusBadge>
                                    </li>
                                );
                            })}
                        </ul>
                    </SectionCard>
                </div>
            </div>

            {/* Hinweisleiste */}
            <div className="mt-6 flex items-start gap-3 rounded-md border border-border bg-surface-sunken px-4 py-3 text-caption text-muted-foreground">
                <Info className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                <div className="flex-1">
                    <span className="font-medium text-foreground">
                        Produktbasis aktiv.
                    </span>{" "}
                    Farben, Typografie (IBM Plex Sans/Mono, 3 Groessen), Spacing
                    (4px-Raster) und Kern-Komponenten sind ausgerollt. Naechster
                    Schritt: Incident-Auswahl. Spec-Referenz:
                    <span className="ml-1 font-mono">
                        /aktuell/els-figma-komponenten-briefing-v0.1.md
                    </span>
                </div>
                <div className="hidden md:flex shrink-0 items-center gap-1.5 rounded-md border border-border bg-background px-2 py-1 text-foreground">
                    <CommandIcon className="h-3 w-3" />
                    <span className="font-mono text-[0.7rem]">K</span>
                    <span className="text-muted-foreground">Kommando-Palette</span>
                </div>
            </div>

            <ConfirmModal
                open={isDemoOpen}
                onOpenChange={setIsDemoOpen}
                title="Demo-Incident starten?"
                description="Es werden Vordaten (Patienten, Transporte, Ressourcen) geladen und ein DEMO-Badge im Header angezeigt. Produktivdaten bleiben unveraendert."
                confirmLabel="Demo starten"
                tone="warning"
                testId="confirm-modal-demo"
            />

            <ConfirmModal
                open={isNewOpen}
                onOpenChange={setIsNewOpen}
                title="Neuen Incident anlegen?"
                description="Der Incident-Anlage-Dialog folgt in Schritt 02 (Name, Typ, Ort, Datum). Dies ist aktuell nur ein Platzhalter."
                confirmLabel="Verstanden"
                tone="default"
                testId="confirm-modal-new"
            />
        </div>
    );
}
