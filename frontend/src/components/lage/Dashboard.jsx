import * as React from "react";
import {
    StatusBadge,
    KpiTile,
    SectionCard
} from "@/components/primitives";
import { Button } from "@/components/ui/button";
import { useIncidents } from "@/context/IncidentContext";
import { getAuswertung } from "@/lib/api";
import {
    AlertTriangle,
    Radio,
    Boxes,
    RefreshCw
} from "lucide-react";
import { toast } from "sonner";

const SICHTUNG_META = {
    S1: { tone: "red", label: "S1", hint: "sofort" },
    S2: { tone: "yellow", label: "S2", hint: "dringend" },
    S3: { tone: "green", label: "S3", hint: "normal" },
    S0: { tone: "gray", label: "S0", hint: "leicht" }
};

const TRANSPORT_STATUS_LABEL = {
    offen: "Offen",
    zugewiesen: "Zugewiesen",
    unterwegs: "Unterwegs",
    abgeschlossen: "Abgeschlossen"
};

function fmtMin(n) {
    if (n === null || n === undefined) return "–";
    return `${Math.round(n)} min`;
}

function ampelFarbe(farbe) {
    return (
        farbe === "red" ? "bg-rose-500" :
        farbe === "orange" ? "bg-orange-500" :
        farbe === "yellow" ? "bg-amber-500" :
        farbe === "green" ? "bg-emerald-500" :
        farbe === "teal" ? "bg-teal-500" :
        farbe === "blue" ? "bg-sky-500" :
        farbe === "indigo" ? "bg-indigo-500" :
        farbe === "purple" ? "bg-violet-500" :
        farbe === "pink" ? "bg-pink-500" : "bg-slate-500"
    );
}

/**
 * Dashboard – schnelle Lage-Uebersicht (KPIs + Sektionen).
 * Selbstladend: zieht sich die Auswertung des aktiven Incidents.
 * Props:
 *   - compact (bool): reduziert Abstaende (fuer Einbettung in Lage-Seite)
 */
export function Dashboard({ compact = false }) {
    const { activeIncident } = useIncidents();
    const incidentId = activeIncident?.id;

    const [auswertung, setAuswertung] = React.useState(null);
    const [loading, setLoading] = React.useState(false);

    const load = React.useCallback(async () => {
        if (!incidentId) return;
        setLoading(true);
        try {
            setAuswertung(await getAuswertung(incidentId));
        } catch (e) {
            toast.error("Auswertung konnte nicht geladen werden");
        } finally {
            setLoading(false);
        }
    }, [incidentId]);

    React.useEffect(() => {
        load();
    }, [load]);

    if (!incidentId) return null;

    if (loading && !auswertung) {
        return (
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4" data-testid="dashboard-loading">
                {Array.from({ length: 8 }).map((_, i) => (
                    <div
                        key={i}
                        className="els-surface h-24 animate-pulse bg-surface-raised/60"
                        aria-hidden
                    />
                ))}
            </div>
        );
    }

    if (!auswertung) return null;

    const a = auswertung.A_patienten;
    const b = auswertung.B_transporte;
    const c = auswertung.C_kommunikation;
    const d = auswertung.D_ressourcen;
    const e = auswertung.E_konflikte;
    const f = auswertung.F_metadaten;
    const g = auswertung.G_abschnitte || { total: 0, abschnitte: [] };
    const bettKpi = a.betten || { total: 0, belegt: 0, frei: 0, gesperrt: 0, auslastung_pct: 0, belegungsdauer_min_avg: 0 };

    return (
        <div className={compact ? "space-y-4" : "space-y-5"} data-testid="lage-dashboard">
            {/* Refresh-Zeile */}
            <div className="flex items-center justify-between">
                <div>
                    <div className="text-caption uppercase tracking-wider text-muted-foreground">
                        Lage-Uebersicht
                    </div>
                    <div className="text-heading">
                        Schnelle Kennzahlen
                    </div>
                </div>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={load}
                    disabled={loading}
                    data-testid="dashboard-refresh"
                >
                    <RefreshCw className={"h-3.5 w-3.5 " + (loading ? "animate-spin" : "")} />
                    Neu laden
                </Button>
            </div>

            {/* Top KPIs */}
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <KpiTile
                    testId="kpi-einsatzdauer"
                    label="Einsatzdauer"
                    value={f.einsatzdauer_min}
                    unit="min"
                    tone="default"
                    hint={f.end_at ? "abgeschlossen" : "laufend"}
                />
                <KpiTile
                    testId="kpi-patienten"
                    label="Patienten gesamt"
                    value={a.total}
                    unit=""
                    tone="default"
                    hint={`${a.status.uebergeben + a.status.entlassen} abgeschlossen`}
                />
                <KpiTile
                    testId="kpi-transporte"
                    label="Transporte"
                    value={b.total}
                    unit=""
                    tone="yellow"
                    hint={`${b.status.abgeschlossen} abgeschlossen`}
                />
                <KpiTile
                    testId="kpi-konflikte"
                    label="Konflikte"
                    value={e.total}
                    unit=""
                    tone={e.rot > 0 ? "red" : e.gelb > 0 ? "yellow" : "green"}
                    hint={`${e.rot} rot · ${e.gelb} gelb`}
                />
            </div>

            {/* Abschnitte + Betten */}
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <KpiTile
                    testId="kpi-abschnitte"
                    label="Abschnitte"
                    value={g.total}
                    unit=""
                    tone="default"
                    hint={`${g.aktiv || 0} aktiv`}
                />
                <KpiTile
                    testId="kpi-betten-auslastung"
                    label="Bett-Auslastung"
                    value={bettKpi.auslastung_pct}
                    unit="%"
                    tone={bettKpi.auslastung_pct > 80 ? "red" : bettKpi.auslastung_pct > 50 ? "yellow" : "green"}
                    hint={`${bettKpi.belegt}/${bettKpi.total} belegt`}
                />
                <KpiTile
                    testId="kpi-betten-dauer"
                    label="Ø Belegungsdauer"
                    value={bettKpi.belegungsdauer_min_avg}
                    unit="min"
                    tone="default"
                />
                <KpiTile
                    testId="kpi-ohne-abschnitt"
                    label="Ress. ohne Abschnitt"
                    value={d.ohne_abschnitt || 0}
                    unit=""
                    tone={(d.ohne_abschnitt_pct || 0) > 20 ? "yellow" : "green"}
                    hint={`${d.ohne_abschnitt_pct || 0}%`}
                />
            </div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                {/* Sichtungsverteilung */}
                <SectionCard
                    title="Sichtungsverteilung"
                    subtitle="Patienten nach Sichtungsstufe"
                    testId="card-sichtung"
                >
                    <div className="grid grid-cols-4 gap-2">
                        {["S1", "S2", "S3", "S0"].map((s) => {
                            const meta = SICHTUNG_META[s];
                            const count = a.sichtung[s] || 0;
                            return (
                                <div
                                    key={s}
                                    className="els-surface flex flex-col items-center gap-1 p-3"
                                    data-testid={`sichtung-count-${s}`}
                                >
                                    <StatusBadge
                                        tone={meta.tone}
                                        variant="solid"
                                        size="sm"
                                        className="font-mono"
                                    >
                                        {meta.label}
                                    </StatusBadge>
                                    <div className="text-kpi tabular-nums">{count}</div>
                                    <div className="text-[0.65rem] uppercase tracking-wider text-muted-foreground">
                                        {meta.hint}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                    {a.sichtung.ohne > 0 && (
                        <div className="mt-3 rounded-md border border-status-yellow/30 bg-status-yellow/10 px-3 py-2 text-caption text-status-yellow">
                            <AlertTriangle className="inline h-3.5 w-3.5 mr-1" />
                            {a.sichtung.ohne} Patient(en) ohne Sichtung
                        </div>
                    )}
                </SectionCard>

                {/* Zeiten */}
                <SectionCard
                    title="Zeiten & Durchsatz"
                    subtitle="Mittelwerte"
                    testId="card-zeiten"
                >
                    <dl className="grid grid-cols-2 gap-y-3 text-body">
                        <dt className="text-muted-foreground">Wartezeit Ø</dt>
                        <dd className="font-mono tabular-nums">
                            {fmtMin(a.wartezeit_min_avg)}
                        </dd>
                        <dt className="text-muted-foreground">Behandlungsdauer Ø</dt>
                        <dd className="font-mono tabular-nums">
                            {fmtMin(a.behandlungsdauer_min_avg)}
                        </dd>
                        <dt className="text-muted-foreground">Fahrtdauer Ø</dt>
                        <dd className="font-mono tabular-nums">
                            {fmtMin(b.fahrtdauer_min_avg)}
                        </dd>
                        <dt className="text-muted-foreground">Quittierdauer Ø</dt>
                        <dd className="font-mono tabular-nums">
                            {fmtMin(c.quittier_dauer_min_avg)}
                        </dd>
                    </dl>
                </SectionCard>

                {/* Transporte */}
                <SectionCard
                    title="Transporte"
                    subtitle={`${b.total} gesamt · ${b.typ.intern} intern · ${b.typ.extern} extern`}
                    testId="card-transporte"
                >
                    <div className="grid grid-cols-2 gap-2 text-body">
                        {Object.entries(b.status).map(([k, v]) => (
                            <div
                                key={k}
                                className="flex items-center justify-between rounded-md bg-surface-raised px-3 py-1.5"
                            >
                                <span className="text-muted-foreground">
                                    {TRANSPORT_STATUS_LABEL[k]}
                                </span>
                                <span className="font-mono tabular-nums">{v}</span>
                            </div>
                        ))}
                    </div>
                </SectionCard>

                {/* Ressourcen + Meldungen */}
                <SectionCard
                    title="Ressourcen & Meldungen"
                    testId="card-ressourcen"
                >
                    <div className="grid grid-cols-2 gap-3 text-body">
                        <div>
                            <div className="text-caption uppercase tracking-wider text-muted-foreground mb-1.5">
                                <Boxes className="inline h-3 w-3 mr-1" />
                                Ressourcen
                            </div>
                            {Object.entries(d.status).map(([k, v]) => (
                                <div
                                    key={k}
                                    className="flex justify-between py-0.5"
                                >
                                    <span className="text-muted-foreground">{k}</span>
                                    <span className="font-mono tabular-nums">{v}</span>
                                </div>
                            ))}
                        </div>
                        <div>
                            <div className="text-caption uppercase tracking-wider text-muted-foreground mb-1.5">
                                <Radio className="inline h-3 w-3 mr-1" />
                                Meldungen
                            </div>
                            <div className="flex justify-between py-0.5">
                                <span className="text-muted-foreground">kritisch</span>
                                <span className="font-mono tabular-nums">
                                    {c.prioritaet.kritisch}
                                </span>
                            </div>
                            <div className="flex justify-between py-0.5">
                                <span className="text-muted-foreground">dringend</span>
                                <span className="font-mono tabular-nums">
                                    {c.prioritaet.dringend}
                                </span>
                            </div>
                            <div className="flex justify-between py-0.5">
                                <span className="text-muted-foreground">normal</span>
                                <span className="font-mono tabular-nums">
                                    {c.prioritaet.normal}
                                </span>
                            </div>
                            <div className="flex justify-between py-0.5 mt-1 border-t border-border pt-1">
                                <span className="text-muted-foreground">offen</span>
                                <span className="font-mono tabular-nums">{c.offen}</span>
                            </div>
                        </div>
                    </div>
                </SectionCard>

                {/* Abschnitte-Uebersicht */}
                {g.abschnitte && g.abschnitte.length > 0 && (
                    <SectionCard
                        title="Einsatzabschnitte"
                        subtitle={`${g.total} Abschnitte · Ressourcen und Betten je Abschnitt`}
                        testId="card-abschnitte"
                    >
                        <ul className="space-y-1.5">
                            {g.abschnitte.map((ab) => (
                                <li
                                    key={ab.id}
                                    className="flex items-center gap-2 rounded-md bg-surface-raised px-3 py-1.5"
                                    data-testid={`dashboard-abschnitt-${ab.id}`}
                                >
                                    <span
                                        aria-hidden
                                        className={"inline-block h-2.5 w-2.5 rounded-full " + ampelFarbe(ab.farbe)}
                                    />
                                    <span className="flex-1 truncate text-body">{ab.name}</span>
                                    <span className="font-mono text-caption text-muted-foreground tabular-nums">
                                        Res {ab.ressourcen_im_einsatz}/{ab.ressourcen_total}
                                    </span>
                                    <span className="font-mono text-caption text-muted-foreground tabular-nums">
                                        Bett {ab.betten_belegt}/{ab.betten_total}
                                    </span>
                                    <StatusBadge
                                        tone={ab.ampel === "red" ? "red" : ab.ampel === "yellow" ? "yellow" : ab.ampel === "green" ? "green" : "gray"}
                                        variant="soft"
                                        size="sm"
                                    >
                                        {ab.ampel === "red" ? "voll" : ab.ampel === "yellow" ? "teilw." : ab.ampel === "green" ? "bereit" : "leer"}
                                    </StatusBadge>
                                </li>
                            ))}
                        </ul>
                    </SectionCard>
                )}
            </div>
        </div>
    );
}
