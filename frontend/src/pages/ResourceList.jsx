import * as React from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue
} from "@/components/ui/select";
import {
    Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle
} from "@/components/ui/dialog";
import { StatusBadge, SectionCard, KpiTile, ConfirmModal } from "@/components/primitives";
import { useOps } from "@/context/OpsContext";
import { useIncidents } from "@/context/IncidentContext";
import { useRole } from "@/context/RoleContext";
import { listAbschnitte, listDiveraVehicles, getDiveraConfigured, updateResource as apiUpdateResource } from "@/lib/api";
import { getFarbe } from "@/lib/abschnitt-meta";
import { fmsMeta } from "@/lib/fms-status";
import {
    RESOURCE_STATUS, RESOURCE_STATUS_KEYS,
    RESOURCE_KATEGORIE, RESOURCE_KAT_KEYS
} from "@/lib/ops-meta";
import { cn } from "@/lib/utils";
import {
    ArrowLeft, Boxes, RefreshCw, Truck, Stethoscope, Users,
    AlertTriangle, Circle, Plus, Edit3, Trash2, RadioTower, Unlink
} from "lucide-react";
import { toast } from "sonner";

const KAT_ICON = {
    uhs: Stethoscope,
    evt: Users,
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

function DiveraInlineSelect({ resource, vehicles, onChange, canEdit }) {
    const linked = resource.divera_id
        ? vehicles.find((v) => String(v.id) === String(resource.divera_id))
        : null;
    const fms = linked?.fmsstatus;
    const meta = fms != null ? fmsMeta(fms) : null;

    return (
        <Select
            value={resource.divera_id ? String(resource.divera_id) : "none"}
            onValueChange={(v) => onChange(resource.id, v === "none" ? null : v)}
            disabled={!canEdit || vehicles.length === 0}
        >
            <SelectTrigger
                className="w-44 h-8 bg-background text-caption"
                data-testid={`resource-divera-select-${resource.id}`}
                title={
                    vehicles.length === 0
                        ? "Keine Divera-Fahrzeuge verfuegbar"
                        : "Mit Divera-Fahrzeug verknuepfen"
                }
            >
                <div className="flex items-center gap-1.5 min-w-0">
                    <RadioTower
                        className={cn(
                            "h-3 w-3 shrink-0",
                            linked ? "text-emerald-500" : "text-muted-foreground/60"
                        )}
                    />
                    {linked ? (
                        <>
                            <span className="truncate font-medium">{linked.name}</span>
                            {meta && (
                                <span
                                    className="ml-auto font-mono text-[10px] font-bold"
                                    style={{ color: meta.color }}
                                >
                                    {fms}
                                </span>
                            )}
                        </>
                    ) : (
                        <span className="text-muted-foreground italic">Divera</span>
                    )}
                </div>
            </SelectTrigger>
            <SelectContent>
                <SelectItem value="none">
                    <span className="inline-flex items-center gap-1.5">
                        <Unlink className="h-3 w-3" />
                        nicht verknuepft
                    </span>
                </SelectItem>
                {vehicles.map((v) => {
                    const vMeta = v.fmsstatus != null ? fmsMeta(v.fmsstatus) : null;
                    return (
                        <SelectItem key={v.id} value={String(v.id)}>
                            <span className="inline-flex items-center gap-2">
                                <span className="font-medium">{v.name}</span>
                                {v.shortname && v.shortname !== v.name && (
                                    <span className="text-muted-foreground text-xs">
                                        ({v.shortname})
                                    </span>
                                )}
                                {vMeta && (
                                    <span
                                        className="ml-auto font-mono text-[10px] font-bold"
                                        style={{ color: vMeta.color }}
                                    >
                                        FMS {v.fmsstatus}
                                    </span>
                                )}
                            </span>
                        </SelectItem>
                    );
                })}
            </SelectContent>
        </Select>
    );
}

function ResourceRow({ resource, abschnitt, abschnitte, vehicles, onChangeStatus, onChangeAbschnitt, onChangeDivera, onEdit, onDelete, canEdit, canDelete }) {
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
            <DiveraInlineSelect
                resource={resource}
                vehicles={vehicles}
                onChange={onChangeDivera}
                canEdit={canEdit}
            />
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
                disabled={Boolean(resource.divera_id)}
            >
                <SelectTrigger
                    className="w-36 h-8 bg-background"
                    data-testid={`resource-status-${resource.id}`}
                    title={resource.divera_id ? "Status wird vom Divera-Polling gesteuert" : ""}
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
            {canEdit && (
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    onClick={() => onEdit(resource)}
                    data-testid={`resource-edit-${resource.id}`}
                    title="Bearbeiten"
                >
                    <Edit3 className="h-3.5 w-3.5" />
                </Button>
            )}
            {canDelete && (
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-status-red"
                    onClick={() => onDelete(resource)}
                    data-testid={`resource-delete-${resource.id}`}
                    title="Loeschen"
                >
                    <Trash2 className="h-3.5 w-3.5" />
                </Button>
            )}
        </div>
    );
}

function ResourceDialog({ open, onOpenChange, initial, abschnitte, vehicles, onSave }) {
    const [form, setForm] = React.useState({
        name: "", typ: "intern", kategorie: "sonstiges",
        status: "verfuegbar", abschnitt_id: null, divera_id: null, notiz: ""
    });
    React.useEffect(() => {
        setForm(initial || {
            name: "", typ: "intern", kategorie: "sonstiges",
            status: "verfuegbar", abschnitt_id: null, divera_id: null, notiz: ""
        });
    }, [initial, open]);
    const isEdit = Boolean(initial?.id);
    const linkedVehicle = form.divera_id
        ? vehicles.find((v) => String(v.id) === String(form.divera_id))
        : null;

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md" data-testid="resource-dialog">
                <DialogHeader>
                    <DialogTitle>{isEdit ? "Ressource bearbeiten" : "Neue Ressource"}</DialogTitle>
                    <DialogDescription>
                        Ressource fuer diesen Incident anlegen oder aendern. Verknuepfung
                        mit Divera-Fahrzeug uebernimmt automatisch Live-FMS-Status.
                    </DialogDescription>
                </DialogHeader>
                <div className="space-y-3">
                    <div>
                        <label className="text-caption text-muted-foreground">Name</label>
                        <Input
                            value={form.name}
                            onChange={(e) => setForm({ ...form, name: e.target.value })}
                            placeholder="z.B. RTW 3, UHS Team 4"
                            data-testid="resource-name-input"
                        />
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                        <div>
                            <label className="text-caption text-muted-foreground">Typ</label>
                            <Select value={form.typ} onValueChange={(v) => setForm({ ...form, typ: v })}>
                                <SelectTrigger data-testid="resource-typ-select">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="intern">Intern</SelectItem>
                                    <SelectItem value="extern">Extern</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                        <div>
                            <label className="text-caption text-muted-foreground">Kategorie</label>
                            <Select value={form.kategorie} onValueChange={(v) => setForm({ ...form, kategorie: v })}>
                                <SelectTrigger data-testid="resource-kat-select">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {RESOURCE_KAT_KEYS.map((k) => (
                                        <SelectItem key={k} value={k}>
                                            {RESOURCE_KATEGORIE[k].label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                        <div>
                            <label className="text-caption text-muted-foreground">Status</label>
                            <Select
                                value={form.status}
                                onValueChange={(v) => setForm({ ...form, status: v })}
                                disabled={Boolean(form.divera_id)}
                            >
                                <SelectTrigger data-testid="resource-status-select">
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
                        <div>
                            <label className="text-caption text-muted-foreground">Abschnitt</label>
                            <Select
                                value={form.abschnitt_id || "none"}
                                onValueChange={(v) => setForm({ ...form, abschnitt_id: v === "none" ? null : v })}
                            >
                                <SelectTrigger data-testid="resource-abschnitt-dialog">
                                    <SelectValue />
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
                        </div>
                    </div>
                    <div>
                        <label className="text-caption text-muted-foreground flex items-center gap-1.5">
                            <RadioTower className="h-3 w-3" />
                            Divera-Fahrzeug verknuepfen
                        </label>
                        <Select
                            value={form.divera_id ? String(form.divera_id) : "none"}
                            onValueChange={(v) => setForm({ ...form, divera_id: v === "none" ? null : v })}
                            disabled={vehicles.length === 0}
                        >
                            <SelectTrigger data-testid="resource-divera-dialog">
                                <SelectValue placeholder="— nicht verknuepft —" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="none">— nicht verknuepft —</SelectItem>
                                {vehicles.map((v) => {
                                    const vMeta = v.fmsstatus != null ? fmsMeta(v.fmsstatus) : null;
                                    return (
                                        <SelectItem key={v.id} value={String(v.id)}>
                                            <span className="inline-flex items-center gap-2">
                                                <span className="font-medium">{v.name}</span>
                                                {v.shortname && v.shortname !== v.name && (
                                                    <span className="text-muted-foreground text-xs">
                                                        ({v.shortname})
                                                    </span>
                                                )}
                                                {vMeta && (
                                                    <span
                                                        className="font-mono text-[10px] font-bold"
                                                        style={{ color: vMeta.color }}
                                                    >
                                                        FMS {v.fmsstatus}
                                                    </span>
                                                )}
                                            </span>
                                        </SelectItem>
                                    );
                                })}
                            </SelectContent>
                        </Select>
                        {vehicles.length === 0 ? (
                            <p className="mt-1 text-[11px] text-muted-foreground italic">
                                Keine Divera-Fahrzeuge verfuegbar (API-Key fehlt oder kein Zugriff).
                                Pruefe DiveraPanel in der Karte.
                            </p>
                        ) : linkedVehicle ? (
                            <p className="mt-1 text-[11px] text-muted-foreground">
                                Verknuepft mit{" "}
                                <span className="font-mono text-foreground">
                                    {linkedVehicle.name}
                                </span>
                                {linkedVehicle.fmsstatus != null && (
                                    <>
                                        {" · aktueller FMS "}
                                        <span
                                            className="font-mono font-semibold"
                                            style={{ color: fmsMeta(linkedVehicle.fmsstatus)?.color }}
                                        >
                                            {linkedVehicle.fmsstatus}
                                        </span>
                                    </>
                                )}
                                {" · Status & FMS werden vom Polling ueberschrieben."}
                            </p>
                        ) : (
                            <p className="mt-1 text-[11px] text-muted-foreground">
                                Bei Verknuepfung werden Status und FMS automatisch alle 30s synchronisiert.
                            </p>
                        )}
                    </div>
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>Abbrechen</Button>
                    <Button
                        onClick={() => {
                            if (!form.name.trim()) {
                                toast.error("Name erforderlich");
                                return;
                            }
                            onSave(form);
                        }}
                        data-testid="resource-save"
                    >
                        {isEdit ? "Speichern" : "Anlegen"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
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
    const { resources, refreshResources, updResource, addResource, rmResource } = useOps();
    const { can } = useRole();
    const [abschnitte, setAbschnitte] = React.useState([]);
    const [vehicles, setVehicles] = React.useState([]);
    const [diveraConfigured, setDiveraConfigured] = React.useState(null);
    const [dialog, setDialog] = React.useState({ open: false, initial: null });
    const [confirmDelete, setConfirmDelete] = React.useState(null);

    const loadAbschnitte = React.useCallback(async () => {
        if (!activeIncident?.id) return;
        try {
            setAbschnitte(await listAbschnitte(activeIncident.id));
        } catch (e) {
            // silent
        }
    }, [activeIncident?.id]);

    const loadVehicles = React.useCallback(async () => {
        try {
            const v = await listDiveraVehicles();
            setVehicles(Array.isArray(v) ? v : []);
        } catch {
            setVehicles([]);
        }
    }, []);

    React.useEffect(() => {
        loadAbschnitte();
    }, [loadAbschnitte]);

    // Divera-Konfiguration einmal pruefen + Fahrzeuge laden + alle 30s refreshen (live FMS)
    React.useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const cfg = await getDiveraConfigured();
                if (cancelled) return;
                setDiveraConfigured(Boolean(cfg?.configured));
                if (cfg?.configured) await loadVehicles();
            } catch {
                if (!cancelled) setDiveraConfigured(false);
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [loadVehicles]);

    React.useEffect(() => {
        if (!diveraConfigured) return undefined;
        const id = setInterval(loadVehicles, 30000);
        return () => clearInterval(id);
    }, [diveraConfigured, loadVehicles]);

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

    const handleChangeDivera = async (id, diveraId) => {
        try {
            await apiUpdateResource(id, { divera_id: diveraId });
            await refreshResources();
            // Fahrzeug-Liste sofort nachladen, damit FMS-Status aktuell ist
            loadVehicles();
            if (diveraId) {
                const v = vehicles.find((x) => String(x.id) === String(diveraId));
                toast.success(
                    v ? `Mit "${v.name}" verknuepft` : "Verknuepfung gesetzt",
                );
            } else {
                toast.success("Verknuepfung entfernt");
            }
        } catch (e) {
            toast.error("Verknuepfung fehlgeschlagen");
        }
    };

    const handleSave = async (form) => {
        try {
            if (dialog.initial?.id) {
                await updResource(dialog.initial.id, form);
                toast.success("Ressource aktualisiert");
            } else {
                await addResource(form);
                toast.success("Ressource angelegt");
            }
            setDialog({ open: false, initial: null });
        } catch (e) {
            toast.error("Speichern fehlgeschlagen");
        }
    };

    const handleDelete = async () => {
        if (!confirmDelete) return;
        try {
            await rmResource(confirmDelete.id);
            toast.success("Ressource geloescht");
        } catch (e) {
            toast.error("Loeschen fehlgeschlagen");
        } finally {
            setConfirmDelete(null);
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
                <div className="flex items-center gap-2">
                    {can("resource.create") && (
                        <Button
                            onClick={() => setDialog({ open: true, initial: null })}
                            data-testid="resource-new-btn"
                        >
                            <Plus className="h-4 w-4" />
                            Ressource anlegen
                        </Button>
                    )}
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

            {/* Divera-Konfigurations-Hinweis */}
            {diveraConfigured === false && (
                <div
                    className="mt-4 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-caption text-amber-300"
                    data-testid="divera-not-configured"
                >
                    <span className="font-medium">Divera 24/7 nicht konfiguriert.</span>{" "}
                    Setze <span className="font-mono">DIVERA_API_KEY</span> in der
                    Backend-Konfiguration, um Fahrzeuge zu verknuepfen.
                </div>
            )}
            {diveraConfigured && vehicles.length === 0 && (
                <div
                    className="mt-4 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-caption text-amber-300"
                    data-testid="divera-no-vehicles"
                >
                    Keine Divera-Fahrzeuge gefunden. Pruefe Zugriffs-Berechtigungen im Divera-Account.
                </div>
            )}

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
                                vehicles={vehicles}
                                onChangeStatus={(id, status) => updResource(id, { status })}
                                onChangeAbschnitt={handleChangeAbschnitt}
                                onChangeDivera={handleChangeDivera}
                                onEdit={(x) => setDialog({ open: true, initial: x })}
                                onDelete={(x) => setConfirmDelete(x)}
                                canEdit={can("resource.update")}
                                canDelete={can("resource.delete")}
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
                                vehicles={vehicles}
                                onChangeStatus={(id, status) => updResource(id, { status })}
                                onChangeAbschnitt={handleChangeAbschnitt}
                                onChangeDivera={handleChangeDivera}
                                onEdit={(x) => setDialog({ open: true, initial: x })}
                                onDelete={(x) => setConfirmDelete(x)}
                                canEdit={can("resource.update")}
                                canDelete={can("resource.delete")}
                            />
                        ))}
                    </div>
                </SectionCard>
            </div>

            <ResourceDialog
                open={dialog.open}
                onOpenChange={(v) => setDialog((d) => ({ ...d, open: v }))}
                initial={dialog.initial}
                abschnitte={abschnitte}
                vehicles={vehicles}
                onSave={handleSave}
            />

            <ConfirmModal
                open={!!confirmDelete}
                onOpenChange={(v) => !v && setConfirmDelete(null)}
                title="Ressource loeschen?"
                description={confirmDelete ? `"${confirmDelete.name}" wird geloescht.` : ""}
                confirmLabel="Loeschen"
                tone="destructive"
                onConfirm={handleDelete}
            />
        </div>
    );
}
