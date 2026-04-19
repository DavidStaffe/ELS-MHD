import * as React from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue
} from "@/components/ui/select";
import { StatusBadge, SectionCard, KpiTile } from "@/components/primitives";
import { useOps } from "@/context/OpsContext";
import { useIncidents } from "@/context/IncidentContext";
import { listAbschnitte, updateResource as apiUpdateResource } from "@/lib/api";
import { getFarbe } from "@/lib/abschnitt-meta";
import {
    RESOURCE_STATUS, RESOURCE_STATUS_KEYS,
    RESOURCE_KATEGORIE, RESOURCE_KAT_KEYS
} from "@/lib/ops-meta";
import { cn } from "@/lib/utils";
import {
    ArrowLeft, Boxes, RefreshCw, Truck, Stethoscope, Bike,
    AlertTriangle, Circle, Layers
} from "lucide-react";

const KAT_ICON = {
    uhs: Stethoscope,
    bike: Bike,
    rtw: Truck,
    ktw: Truck,
    nef: AlertTriangle,
    sonstiges: Boxes
};

function AbschnittChip({ abschnitt }) {
    if (!abschnitt) {
        return (
            <span className="inline-flex items-center gap-1 rounded bg-surface-raised px-1.5 py-0.5 text-[0.65rem] text-muted-foreground">
                <span className="h-1.5 w-1.5 rounded-full bg-status-gray" />
                kein Abschnitt
            </span>
        );
    }
    const farbe = getFarbe(abschnitt.farbe);
    return (
        <span
            className={cn(
                "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[0.65rem]",
                farbe.soft
            )}
            data-testid={`res-abschnitt-${abschnitt.id}`}
        >
            <span className={cn("h-1.5 w-1.5 rounded-full", farbe.dot)} />
            {abschnitt.name}
        </span>
    );
}

function ResourceRow({ resource, abschnitt, abschnitte, onChangeStatus, onChangeAbschnitt }) {
    const meta = RESOURCE_STATUS[resource.status] || { label: resource.status, tone: "neutral" };
    const KatIcon = KAT_ICON[resource.kategorie] || Boxes;
    return (
        <div
            data-testid={`resource-row-${resource.id}`}
            className="els-surface flex items-center gap-3 px-3 py-2"
        >
            <KatIcon className="h-4 w-4 shrink-0 text-primary" />
            <div className="min-w-0 flex-1">
                <div className="text-body font-medium truncate">{resource.name}</div>
                <div className="flex items-center gap-1.5 text-caption text-muted-foreground">
                    <span>
                        {RESOURCE_KATEGORIE[resource.kategorie]?.label} ·{" "}
                        {resource.typ === "intern" ? "Intern" : "Extern"}
                    </span>
                    <AbschnittChip abschnitt={abschnitt} />
                </div>
            </div>
            <Select
                value={resource.abschnitt_id || "none"}
                onValueChange={(v) => onChangeAbschnitt(resource.id, v === "none" ? null : v)}
            >
                <SelectTrigger
                    className="w-28 h-8 bg-background text-caption"
                    data-testid={`resource-abschnitt-select-${resource.id}`}
                >
                    <SelectValue placeholder="Abschnitt" />
                </SelectTrigger>
                <SelectContent>
                    <SelectItem value="none">(keiner)</SelectItem>
                    {abschnitte.map((a) => (
                        <SelectItem key={a.id} value={a.id}>
                            {a.name}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
            <StatusBadge tone={meta.tone} variant="soft" size="sm">
                {meta.label}
            </StatusBadge>
            <Select
                value={resource.status}
                onValueChange={(v) => onChangeStatus(resource.id, v)}
            >
                <SelectTrigger
                    className="w-36 h-8 bg-background"
                    data-testid={`resource-status-${resource.id}`}
                >
                    <SelectValue />
                </SelectTrigger>
                <SelectContent>
                    {RESOURCE_STATUS_KEYS.map((k) => (
                        <SelectItem key={k} value={k}>
                            {RESOURCE_STATUS[k].label}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
        </div>
    );
}

function StatusMatrix({ resources }) {
    // Reihen = Kategorien, Spalten = Status
    const cells = React.useMemo(() => {
        const map = {};
        for (const k of RESOURCE_KAT_KEYS) {
            map[k] = Object.fromEntries(RESOURCE_STATUS_KEYS.map((s) => [s, []]));
        }
        for (const r of resources) {
            const kat = map[r.kategorie] || map.sonstiges;
            if (kat[r.status]) kat[r.status].push(r);
        }
        return map;
    }, [resources]);

    const katsPresent = RESOURCE_KAT_KEYS.filter((k) =>
        resources.some((r) => r.kategorie === k)
    );

    const toneCell = (tone, count) =>
        count === 0
            ? "bg-surface-sunken text-muted-foreground/60"
            : tone === "red"
                ? "bg-status-red/15 text-status-red border-status-red/30"
                : tone === "yellow"
                    ? "bg-status-yellow/15 text-status-yellow border-status-yellow/30"
                    : tone === "green"
                        ? "bg-status-green/15 text-status-green border-status-green/30"
                        : tone === "info"
                            ? "bg-primary/15 text-primary border-primary/30"
                            : "bg-muted/30 text-foreground";

    return (
        <div data-testid="resource-matrix" className="overflow-x-auto">
            <table className="w-full border-collapse text-body">
                <thead className="bg-surface-sunken">
                    <tr>
                        <th className="text-caption font-medium uppercase tracking-wider text-muted-foreground border-b border-border px-3 py-2 text-left">
                            Kategorie
                        </th>
                        {RESOURCE_STATUS_KEYS.map((s) => {
                            const m = RESOURCE_STATUS[s];
                            return (
                                <th
                                    key={s}
                                    className="text-caption font-medium uppercase tracking-wider text-muted-foreground border-b border-border px-3 py-2 text-center"
                                >
                                    {m.label}
                                </th>
                            );
                        })}
                    </tr>
                </thead>
                <tbody>
                    {katsPresent.length === 0 && (
                        <tr>
                            <td colSpan={5} className="px-3 py-6 text-center text-caption text-muted-foreground">
                                Keine Ressourcen vorhanden
                            </td>
                        </tr>
                    )}
                    {katsPresent.map((kat) => {
                        const KatIcon = KAT_ICON[kat] || Boxes;
                        return (
                            <tr key={kat} className="border-b border-border last:border-0">
                                <td className="px-3 py-2">
                                    <div className="flex items-center gap-2">
                                        <KatIcon className="h-4 w-4 text-primary" />
                                        <span className="font-medium">
                                            {RESOURCE_KATEGORIE[kat]?.label}
                                        </span>
                                    </div>
                                </td>
                                {RESOURCE_STATUS_KEYS.map((s) => {
                                    const items = cells[kat][s];
                                    const count = items.length;
                                    const tone = RESOURCE_STATUS[s].tone;
                                    return (
                                        <td
                                            key={s}
                                            className="px-2 py-1.5 text-center"
                                            data-testid={`matrix-cell-${kat}-${s}`}
                                        >
                                            <div
                                                className={cn(
                                                    "inline-flex min-w-[3rem] items-center justify-center gap-1 rounded-md border px-2 py-1 font-mono tabular-nums transition-colors",
                                                    toneCell(tone, count)
                                                )}
                                                title={items.map((x) => x.name).join(", ") || "—"}
                                            >
                                                <Circle
                                                    className={cn(
                                                        "h-2 w-2 fill-current",
                                                        count === 0 && "opacity-30"
                                                    )}
                                                />
                                                <span className="font-semibold">{count}</span>
                                            </div>
                                        </td>
                                    );
                                })}
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}

export default function ResourceList() {
    const navigate = useNavigate();
    const { activeIncident } = useIncidents();
    const { resources, refreshResources, updResource } = useOps();
    const [abschnitte, setAbschnitte] = React.useState([]);

    const loadAbschnitte = React.useCallback(async () => {
        if (!activeIncident?.id) return;
        try {
            setAbschnitte(await listAbschnitte(activeIncident.id));
        } catch (e) {
            // silent
        }
    }, [activeIncident?.id]);

    React.useEffect(() => {
        loadAbschnitte();
    }, [loadAbschnitte]);

    const abschnittById = React.useMemo(() => {
        const m = new Map();
        for (const a of abschnitte) m.set(a.id, a);
        return m;
    }, [abschnitte]);

    const handleChangeAbschnitt = async (id, abschnittId) => {
        try {
            await apiUpdateResource(id, { abschnitt_id: abschnittId });
            await refreshResources();
        } catch (e) {
            // ignore
        }
    };

    const kpis = React.useMemo(() => {
        const b = { total: resources.length };
        for (const k of RESOURCE_STATUS_KEYS) b[k] = 0;
        for (const r of resources) {
            if (b[r.status] !== undefined) b[r.status]++;
        }
        return b;
    }, [resources]);

    if (!activeIncident) {
        return (
            <div className="mx-auto max-w-xl p-6">
                <div className="els-surface p-6 text-center" data-testid="resources-no-incident">
                    <h2 className="text-display">Kein Incident aktiv</h2>
                    <Button className="mt-4" onClick={() => navigate("/")}>
                        <ArrowLeft className="h-4 w-4" />
                        Incident-Uebersicht
                    </Button>
                </div>
            </div>
        );
    }

    const intern = resources.filter((r) => r.typ === "intern");
    const extern = resources.filter((r) => r.typ === "extern");

    return (
        <div className="mx-auto w-full max-w-[1400px] px-6 py-6">
            <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
                <div>
                    <div className="text-caption uppercase tracking-wider text-muted-foreground">
                        Schritt 06 · Ressourcen
                    </div>
                    <h1 className="mt-1 text-display" data-testid="resources-title">
                        Ressourcen-Uebersicht
                    </h1>
                    <p className="text-caption text-muted-foreground">
                        {activeIncident.name}
                    </p>
                </div>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={refreshResources}
                    data-testid="resources-refresh"
                >
                    <RefreshCw className="h-4 w-4" />
                    Aktualisieren
                </Button>
            </div>

            <div className="mb-4 grid grid-cols-2 gap-2 md:grid-cols-5">
                <KpiTile label="Gesamt" value={kpis.total} tone="default" testId="kpi-res-total" />
                <KpiTile label="Verfuegbar" value={kpis.verfuegbar} tone="green" testId="kpi-res-verf" />
                <KpiTile label="Im Einsatz" value={kpis.im_einsatz} tone="default" testId="kpi-res-einsatz" />
                <KpiTile label="Wartung" value={kpis.wartung} tone="yellow" testId="kpi-res-wartung" />
                <KpiTile label="Offline" value={kpis.offline} tone="gray" testId="kpi-res-offline" />
            </div>

            <SectionCard
                title="Statusmatrix"
                subtitle="Kategorien × Status · Zahl = Anzahl Ressourcen je Zelle"
                testId="section-matrix"
                padded={false}
            >
                <StatusMatrix resources={resources} />
            </SectionCard>

            <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
                <SectionCard title="Intern" testId="section-intern" padded={false}>
                    <div className="flex flex-col gap-1.5 p-2">
                        {intern.length === 0 && (
                            <div className="px-3 py-4 text-center text-caption text-muted-foreground">
                                Keine internen Ressourcen
                            </div>
                        )}
                        {intern.map((r) => (
                            <ResourceRow
                                key={r.id}
                                resource={r}
                                abschnitt={r.abschnitt_id ? abschnittById.get(r.abschnitt_id) : null}
                                abschnitte={abschnitte}
                                onChangeStatus={(id, status) => updResource(id, { status })}
                                onChangeAbschnitt={handleChangeAbschnitt}
                            />
                        ))}
                    </div>
                </SectionCard>
                <SectionCard title="Extern" testId="section-extern" padded={false}>
                    <div className="flex flex-col gap-1.5 p-2">
                        {extern.length === 0 && (
                            <div className="px-3 py-4 text-center text-caption text-muted-foreground">
                                Keine externen Ressourcen
                            </div>
                        )}
                        {extern.map((r) => (
                            <ResourceRow
                                key={r.id}
                                resource={r}
                                abschnitt={r.abschnitt_id ? abschnittById.get(r.abschnitt_id) : null}
                                abschnitte={abschnitte}
                                onChangeStatus={(id, status) => updResource(id, { status })}
                                onChangeAbschnitt={handleChangeAbschnitt}
                            />
                        ))}
                    </div>
                </SectionCard>
            </div>
        </div>
    );
}
