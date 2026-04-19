import * as React from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { StatusBadge, KpiTile, SectionCard } from "@/components/primitives";
import { useOps } from "@/context/OpsContext";
import { useIncidents } from "@/context/IncidentContext";
import { KONFLIKT_SCHWERE } from "@/lib/ops-meta";
import { formatDateTime, formatDuration } from "@/lib/time";
import { cn } from "@/lib/utils";
import {
    ArrowLeft, AlertOctagon, RefreshCw, ShieldCheck, ArrowRight, ShieldAlert, Info
} from "lucide-react";

const SCHWERE_ICON = {
    rot: ShieldAlert,
    gelb: AlertOctagon,
    info: Info
};

function KonfliktCard({ k, onResolve, onOpenBezug }) {
    const meta = KONFLIKT_SCHWERE[k.schwere] || { label: k.schwere, tone: "neutral" };
    const Icon = SCHWERE_ICON[k.schwere] || AlertOctagon;
    const [now, setNow] = React.useState(Date.now());
    React.useEffect(() => {
        const id = setInterval(() => setNow(Date.now()), 30000);
        return () => clearInterval(id);
    }, []);
    const seitMs = k.seit ? now - new Date(k.seit).getTime() : null;
    return (
        <article
            data-testid={`konflikt-card-${k.id}`}
            data-schwere={k.schwere}
            className={cn(
                "els-surface relative flex flex-col gap-2 p-3",
                k.schwere === "rot" && "border-status-red/50 bg-status-red/5",
                k.schwere === "gelb" && "border-status-yellow/40 bg-status-yellow/5"
            )}
        >
            <span
                aria-hidden
                className={cn(
                    "absolute left-0 top-0 h-full w-1",
                    k.schwere === "rot" && "bg-status-red",
                    k.schwere === "gelb" && "bg-status-yellow",
                    k.schwere === "info" && "bg-primary"
                )}
            />
            <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2">
                    <Icon
                        className={cn(
                            "h-4 w-4",
                            k.schwere === "rot" && "text-status-red",
                            k.schwere === "gelb" && "text-status-yellow",
                            k.schwere === "info" && "text-primary"
                        )}
                    />
                    <h3 className="text-heading">{k.titel}</h3>
                </div>
                <StatusBadge tone={meta.tone} variant="soft" size="sm">
                    {meta.label}
                </StatusBadge>
            </div>
            <p className="text-body text-muted-foreground">{k.beschreibung}</p>
            <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3 text-caption text-muted-foreground">
                    {k.seit && (
                        <span>
                            seit{" "}
                            <span className="font-mono tabular-nums text-foreground">
                                {formatDuration(seitMs)}
                            </span>
                        </span>
                    )}
                    {k.bezug_label && (
                        <span>
                            Bezug:{" "}
                            <span className="font-mono font-medium text-foreground">
                                {k.bezug_label}
                            </span>
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-1">
                    {k.bezug_typ && k.bezug_id && (
                        <Button
                            size="sm"
                            variant="outline"
                            onClick={() => onOpenBezug(k)}
                            data-testid={`konflikt-open-${k.id}`}
                        >
                            Oeffnen
                            <ArrowRight className="h-3.5 w-3.5" />
                        </Button>
                    )}
                    {k.bezug_typ === "message" && (
                        <Button
                            size="sm"
                            onClick={() => onResolve(k)}
                            data-testid={`konflikt-resolve-${k.id}`}
                        >
                            <ShieldCheck className="h-3.5 w-3.5" />
                            Quittieren
                        </Button>
                    )}
                </div>
            </div>
        </article>
    );
}

export default function KonfliktList() {
    const navigate = useNavigate();
    const { activeIncident } = useIncidents();
    const { konflikte, refreshKonflikte, ackMsg } = useOps();

    const kpis = React.useMemo(() => {
        const k = { total: konflikte.length, rot: 0, gelb: 0, info: 0 };
        for (const x of konflikte) {
            if (k[x.schwere] !== undefined) k[x.schwere]++;
        }
        return k;
    }, [konflikte]);

    if (!activeIncident) {
        return (
            <div className="mx-auto max-w-xl p-6">
                <div className="els-surface p-6 text-center" data-testid="konflikte-no-incident">
                    <h2 className="text-display">Kein Incident aktiv</h2>
                    <Button className="mt-4" onClick={() => navigate("/")}>
                        <ArrowLeft className="h-4 w-4" />Incident-Uebersicht
                    </Button>
                </div>
            </div>
        );
    }

    const handleOpen = (k) => {
        if (k.bezug_typ === "patient") navigate(`/patienten/${k.bezug_id}`);
        else if (k.bezug_typ === "transport") navigate(`/transport`);
        else if (k.bezug_typ === "message") navigate(`/kommunikation`);
    };

    const handleResolve = async (k) => {
        if (k.bezug_typ === "message" && k.bezug_id) {
            await ackMsg(k.bezug_id);
            refreshKonflikte();
        }
    };

    return (
        <div className="mx-auto w-full max-w-[1200px] px-6 py-6">
            <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
                <div>
                    <div className="text-caption uppercase tracking-wider text-muted-foreground">
                        Schritt 06 · Konflikte
                    </div>
                    <h1 className="mt-1 text-display" data-testid="konflikte-title">
                        Konflikte &amp; Blocker
                    </h1>
                    <p className="text-caption text-muted-foreground">
                        Automatische Erkennung · aktualisiert alle 30s ·{" "}
                        {activeIncident.name}
                    </p>
                </div>
                <Button variant="ghost" size="sm" onClick={refreshKonflikte} data-testid="konflikte-refresh">
                    <RefreshCw className="h-4 w-4" />Jetzt pruefen
                </Button>
            </div>

            <div className="mb-4 grid grid-cols-2 gap-2 md:grid-cols-4">
                <KpiTile label="Gesamt" value={kpis.total} tone="default" testId="kpi-kon-total" />
                <KpiTile label="Kritisch" value={kpis.rot} tone="red" testId="kpi-kon-rot" />
                <KpiTile label="Warnung" value={kpis.gelb} tone="yellow" testId="kpi-kon-gelb" />
                <KpiTile label="Info" value={kpis.info} tone="default" testId="kpi-kon-info" />
            </div>

            {konflikte.length === 0 ? (
                <SectionCard testId="konflikte-empty">
                    <div className="flex flex-col items-center gap-2 py-10 text-center">
                        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-status-green/15 text-status-green">
                            <ShieldCheck className="h-6 w-6" />
                        </div>
                        <h3 className="text-heading">Keine offenen Konflikte</h3>
                        <p className="max-w-md text-caption text-muted-foreground">
                            Aktuell wurden keine Blocker erkannt. Wir pruefen
                            kontinuierlich auf wartende S1-Patienten, offene
                            Transporte, lange Fahrten und unquittierte
                            kritische Meldungen.
                        </p>
                    </div>
                </SectionCard>
            ) : (
                <div className="flex flex-col gap-2">
                    {konflikte.map((k) => (
                        <KonfliktCard
                            key={k.id}
                            k={k}
                            onResolve={handleResolve}
                            onOpenBezug={handleOpen}
                        />
                    ))}
                </div>
            )}
        </div>
    );
}
