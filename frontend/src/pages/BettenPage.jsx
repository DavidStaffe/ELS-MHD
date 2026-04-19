import * as React from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter
} from "@/components/ui/dialog";
import {
    Select,
    SelectTrigger,
    SelectValue,
    SelectContent,
    SelectItem
} from "@/components/ui/select";
import { StatusBadge, FilterChip, SichtungBadge, ConfirmModal } from "@/components/primitives";
import { useIncidents } from "@/context/IncidentContext";
import { usePatients } from "@/context/PatientContext";
import { useRole } from "@/context/RoleContext";
import {
    listBetten,
    createBett,
    createBettenBulk,
    updateBett,
    deleteBett,
    assignBett,
    releaseBett,
    listAbschnitte
} from "@/lib/api";
import { BETT_TYPEN, BETT_STATUS, BETT_TYP_KEYS, getFarbe } from "@/lib/abschnitt-meta";
import { cn } from "@/lib/utils";
import {
    Plus,
    Bed,
    Armchair,
    Zap,
    Eye,
    Box,
    UserPlus,
    UserMinus,
    Lock,
    Unlock,
    Trash2,
    Edit3,
    ArrowLeft,
    Zap as Bolt,
    Layers
} from "lucide-react";
import { toast } from "sonner";

const TYP_ICON = {
    liegend: Bed,
    sitzend: Armchair,
    schockraum: Zap,
    beobachtung: Eye,
    sonstiges: Box
};

function StatusChipColor({ status }) {
    if (status === "frei") return "bg-status-green/20 border-status-green/40";
    if (status === "belegt") return "bg-status-red/20 border-status-red/40";
    return "bg-status-gray/20 border-status-gray/40";
}

/* -------------------------------------------------------------------- */
/* Dialog: Einzel + Bulk                                                */
/* -------------------------------------------------------------------- */
function BettDialog({ open, onOpenChange, initial, abschnitte, onSave }) {
    const [form, setForm] = React.useState({
        name: "",
        typ: "liegend",
        status: "frei",
        abschnitt_id: null,
        notiz: ""
    });
    React.useEffect(() => {
        setForm(
            initial || { name: "", typ: "liegend", status: "frei", abschnitt_id: null, notiz: "" }
        );
    }, [initial, open]);
    const isEdit = Boolean(initial?.id);

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md" data-testid="bett-dialog">
                <DialogHeader>
                    <DialogTitle>{isEdit ? "Bett bearbeiten" : "Neues Bett"}</DialogTitle>
                    <DialogDescription>
                        Behandlungsplatz im UHS / Einsatzbereich.
                    </DialogDescription>
                </DialogHeader>
                <div className="space-y-3">
                    <div>
                        <label className="text-caption text-muted-foreground">Name</label>
                        <Input
                            value={form.name}
                            onChange={(e) => setForm({ ...form, name: e.target.value })}
                            placeholder="z.B. Bett 1, Liege 3, Schockraum"
                            data-testid="bett-name-input"
                        />
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                        <div>
                            <label className="text-caption text-muted-foreground">Typ</label>
                            <Select value={form.typ} onValueChange={(v) => setForm({ ...form, typ: v })}>
                                <SelectTrigger data-testid="bett-typ-select">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {BETT_TYP_KEYS.map((k) => (
                                        <SelectItem key={k} value={k}>
                                            {BETT_TYPEN[k].label}
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
                                <SelectTrigger data-testid="bett-abschnitt-select">
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
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>
                        Abbrechen
                    </Button>
                    <Button
                        onClick={() => {
                            if (!form.name.trim()) {
                                toast.error("Name erforderlich");
                                return;
                            }
                            onSave(form);
                        }}
                        data-testid="bett-save"
                    >
                        {isEdit ? "Speichern" : "Anlegen"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

function BulkDialog({ open, onOpenChange, abschnitte, onBulk }) {
    const [form, setForm] = React.useState({
        anzahl: 4,
        typ: "liegend",
        praefix: "Bett",
        abschnitt_id: null,
        start_index: 1
    });
    React.useEffect(() => {
        if (open) setForm({ anzahl: 4, typ: "liegend", praefix: "Bett", abschnitt_id: null, start_index: 1 });
    }, [open]);

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md" data-testid="bulk-dialog">
                <DialogHeader>
                    <DialogTitle>Schnell-Setup</DialogTitle>
                    <DialogDescription>
                        Mehrere Betten in einem Schritt anlegen. Auto-Benennung: "Praefix 1, 2, ...".
                    </DialogDescription>
                </DialogHeader>
                <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-2">
                        <div>
                            <label className="text-caption text-muted-foreground">Anzahl</label>
                            <Input
                                type="number"
                                min={1}
                                max={50}
                                value={form.anzahl}
                                onChange={(e) => setForm({ ...form, anzahl: parseInt(e.target.value || "1", 10) })}
                                data-testid="bulk-anzahl"
                            />
                        </div>
                        <div>
                            <label className="text-caption text-muted-foreground">Typ</label>
                            <Select value={form.typ} onValueChange={(v) => setForm({ ...form, typ: v })}>
                                <SelectTrigger data-testid="bulk-typ">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {BETT_TYP_KEYS.map((k) => (
                                        <SelectItem key={k} value={k}>
                                            {BETT_TYPEN[k].label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                        <div>
                            <label className="text-caption text-muted-foreground">Praefix</label>
                            <Input
                                value={form.praefix}
                                onChange={(e) => setForm({ ...form, praefix: e.target.value })}
                                data-testid="bulk-praefix"
                            />
                        </div>
                        <div>
                            <label className="text-caption text-muted-foreground">Abschnitt</label>
                            <Select
                                value={form.abschnitt_id || "none"}
                                onValueChange={(v) => setForm({ ...form, abschnitt_id: v === "none" ? null : v })}
                            >
                                <SelectTrigger data-testid="bulk-abschnitt">
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
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>
                        Abbrechen
                    </Button>
                    <Button onClick={() => onBulk(form)} data-testid="bulk-save">
                        {form.anzahl} Betten anlegen
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

/* -------------------------------------------------------------------- */
/* Patient-Assign Modal                                                 */
/* -------------------------------------------------------------------- */
function AssignPatientDialog({ open, onOpenChange, patients, onAssign }) {
    const eligible = patients.filter(
        (p) => ["wartend", "in_behandlung"].includes(p.status) && !p.bett_id
    );
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md max-h-[70vh] overflow-hidden flex flex-col" data-testid="assign-dialog">
                <DialogHeader>
                    <DialogTitle>Patient zuweisen</DialogTitle>
                    <DialogDescription>
                        Waehle einen Patienten ohne Bett-Zuweisung.
                    </DialogDescription>
                </DialogHeader>
                <div className="flex-1 overflow-y-auto">
                    {eligible.length === 0 ? (
                        <div className="text-caption text-muted-foreground py-4 text-center">
                            Keine passenden Patienten vorhanden.
                        </div>
                    ) : (
                        <ul className="space-y-1.5">
                            {eligible.map((p) => (
                                <li key={p.id}>
                                    <button
                                        type="button"
                                        onClick={() => onAssign(p.id)}
                                        className="flex w-full items-center gap-2 rounded-md bg-surface-raised px-3 py-2 text-left hover:border-primary/60 hover:bg-primary/10 border border-transparent transition-colors els-focus-ring"
                                        data-testid={`assign-patient-${p.id}`}
                                    >
                                        {p.sichtung ? (
                                            <SichtungBadge level={p.sichtung} size="sm" />
                                        ) : (
                                            <StatusBadge tone="gray" variant="soft" size="sm">–</StatusBadge>
                                        )}
                                        <div className="flex-1 min-w-0">
                                            <div className="font-mono text-body">{p.kennung}</div>
                                            <div className="text-caption text-muted-foreground truncate">
                                                {p.notiz || `Status: ${p.status}`}
                                            </div>
                                        </div>
                                    </button>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            </DialogContent>
        </Dialog>
    );
}

/* -------------------------------------------------------------------- */
/* Bett-Kachel                                                          */
/* -------------------------------------------------------------------- */
function BettKachel({ bett, patient, abschnitt, onAssignClick, onRelease, onLock, onUnlock, onDelete, onEdit, canAssign, canEdit, canDelete, canLock }) {
    const Icon = TYP_ICON[bett.typ] || Bed;
    const farbe = abschnitt ? getFarbe(abschnitt.farbe) : null;
    const [now, setNow] = React.useState(Date.now());
    React.useEffect(() => {
        if (bett.status !== "belegt" || !bett.belegt_seit) return undefined;
        const id = setInterval(() => setNow(Date.now()), 30 * 1000);
        return () => clearInterval(id);
    }, [bett.status, bett.belegt_seit]);

    let dauer = null;
    if (bett.belegt_seit) {
        const diff = now - new Date(bett.belegt_seit).getTime();
        const min = Math.max(0, Math.floor(diff / 60000));
        dauer = min >= 60 ? `${Math.floor(min / 60)}h ${min % 60}min` : `${min} min`;
    }

    return (
        <div
            className={cn(
                "els-surface relative overflow-hidden p-4 border-2 transition-colors",
                StatusChipColor({ status: bett.status })
            )}
            data-testid={`bett-kachel-${bett.id}`}
        >
            {/* Abschnitt-Farbpunkt */}
            {abschnitt && (
                <span
                    aria-hidden
                    className={cn("absolute right-3 top-3 h-2 w-2 rounded-full", farbe.dot)}
                    title={abschnitt.name}
                />
            )}

            {/* Kopfzeile */}
            <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                    <Icon className="h-4 w-4 text-muted-foreground shrink-0" />
                    <div className="min-w-0">
                        <div className="text-heading truncate" data-testid={`bett-name-${bett.id}`}>{bett.name}</div>
                        <div className="text-caption text-muted-foreground">
                            {BETT_TYPEN[bett.typ]?.label}
                            {abschnitt && ` · ${abschnitt.name}`}
                        </div>
                    </div>
                </div>
                <StatusBadge tone={BETT_STATUS[bett.status]?.tone} variant="soft" size="sm">
                    {BETT_STATUS[bett.status]?.label}
                </StatusBadge>
            </div>

            {/* Body abhaengig vom Status */}
            <div className="mt-3">
                {bett.status === "belegt" && patient && (
                    <div className="flex items-center gap-2 rounded-md bg-status-red/10 p-2" data-testid={`bett-patient-${bett.id}`}>
                        {patient.sichtung && <SichtungBadge level={patient.sichtung} size="sm" />}
                        <div className="flex-1 min-w-0">
                            <div className="font-mono text-body">{patient.kennung}</div>
                            <div className="text-caption text-muted-foreground">
                                belegt seit {dauer || "–"}
                            </div>
                        </div>
                    </div>
                )}
                {bett.status === "frei" && (
                    <div className="text-caption text-muted-foreground italic">
                        Bereit fuer Zuweisung
                    </div>
                )}
                {bett.status === "gesperrt" && (
                    <div className="text-caption text-muted-foreground italic">
                        Gesperrt {bett.notiz ? `· ${bett.notiz}` : ""}
                    </div>
                )}
            </div>

            {/* Aktionen */}
            <div className="mt-3 flex flex-wrap gap-1.5">
                {bett.status === "frei" && canAssign && (
                    <Button
                        size="sm"
                        onClick={() => onAssignClick(bett)}
                        data-testid={`bett-assign-${bett.id}`}
                    >
                        <UserPlus className="h-3 w-3" />
                        Zuweisen
                    </Button>
                )}
                {bett.status === "belegt" && canAssign && (
                    <Button
                        size="sm"
                        variant="outline"
                        onClick={() => onRelease(bett)}
                        data-testid={`bett-release-${bett.id}`}
                    >
                        <UserMinus className="h-3 w-3" />
                        Freigeben
                    </Button>
                )}
                {canLock && bett.status === "frei" && (
                    <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => onLock(bett)}
                        data-testid={`bett-lock-${bett.id}`}
                    >
                        <Lock className="h-3 w-3" />
                        Sperren
                    </Button>
                )}
                {canLock && bett.status === "gesperrt" && (
                    <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => onUnlock(bett)}
                        data-testid={`bett-unlock-${bett.id}`}
                    >
                        <Unlock className="h-3 w-3" />
                        Entsperren
                    </Button>
                )}
                {canEdit && (
                    <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => onEdit(bett)}
                        title="Bearbeiten"
                        data-testid={`bett-edit-${bett.id}`}
                    >
                        <Edit3 className="h-3 w-3" />
                    </Button>
                )}
                {canDelete && bett.status !== "belegt" && (
                    <Button
                        size="sm"
                        variant="ghost"
                        className="text-status-red"
                        onClick={() => onDelete(bett)}
                        title="Loeschen"
                        data-testid={`bett-delete-${bett.id}`}
                    >
                        <Trash2 className="h-3 w-3" />
                    </Button>
                )}
            </div>
        </div>
    );
}

/* -------------------------------------------------------------------- */
/* PAGE                                                                 */
/* -------------------------------------------------------------------- */
export default function BettenPage() {
    const navigate = useNavigate();
    const { activeIncident } = useIncidents();
    const { patients, refresh: refreshPatients } = usePatients();
    const { can } = useRole();

    const [betten, setBetten] = React.useState([]);
    const [abschnitte, setAbschnitte] = React.useState([]);
    const [loading, setLoading] = React.useState(false);
    const [bettDialog, setBettDialog] = React.useState({ open: false, initial: null });
    const [bulkOpen, setBulkOpen] = React.useState(false);
    const [assignOpen, setAssignOpen] = React.useState({ open: false, bett: null });
    const [confirmDelete, setConfirmDelete] = React.useState(null);
    const [filter, setFilter] = React.useState("alle");

    const incidentId = activeIncident?.id;

    const loadAll = React.useCallback(async () => {
        if (!incidentId) return;
        setLoading(true);
        try {
            const [b, a] = await Promise.all([listBetten(incidentId), listAbschnitte(incidentId)]);
            setBetten(b);
            setAbschnitte(a);
        } catch (e) {
            toast.error("Laden fehlgeschlagen");
        } finally {
            setLoading(false);
        }
    }, [incidentId]);

    React.useEffect(() => {
        loadAll();
    }, [loadAll]);

    const patientById = React.useMemo(() => {
        const m = new Map();
        for (const p of patients) m.set(p.id, p);
        return m;
    }, [patients]);

    const abschnittById = React.useMemo(() => {
        const m = new Map();
        for (const a of abschnitte) m.set(a.id, a);
        return m;
    }, [abschnitte]);

    const filtered = React.useMemo(() => {
        if (filter === "alle") return betten;
        if (filter === "frei" || filter === "belegt" || filter === "gesperrt")
            return betten.filter((b) => b.status === filter);
        if (filter.startsWith("ab-")) {
            const id = filter.slice(3);
            return betten.filter((b) => b.abschnitt_id === id);
        }
        if (filter === "ohne-abschnitt") return betten.filter((b) => !b.abschnitt_id);
        return betten;
    }, [betten, filter]);

    const counts = React.useMemo(() => {
        return {
            alle: betten.length,
            frei: betten.filter((b) => b.status === "frei").length,
            belegt: betten.filter((b) => b.status === "belegt").length,
            gesperrt: betten.filter((b) => b.status === "gesperrt").length
        };
    }, [betten]);

    /* Handler */
    const handleSave = async (form) => {
        try {
            if (bettDialog.initial?.id) {
                const updated = await updateBett(bettDialog.initial.id, form);
                setBetten((l) => l.map((b) => (b.id === updated.id ? updated : b)));
                toast.success("Bett aktualisiert");
            } else {
                const created = await createBett(incidentId, form);
                setBetten((l) => [...l, created]);
                toast.success("Bett angelegt");
            }
            setBettDialog({ open: false, initial: null });
        } catch (e) {
            toast.error("Speichern fehlgeschlagen");
        }
    };

    const handleBulk = async (form) => {
        try {
            const created = await createBettenBulk(incidentId, form);
            setBetten((l) => [...l, ...created]);
            toast.success(`${created.length} Betten angelegt`);
            setBulkOpen(false);
        } catch (e) {
            toast.error("Bulk-Anlage fehlgeschlagen");
        }
    };

    const handleAssignPatient = async (patientId) => {
        if (!assignOpen.bett) return;
        try {
            const updated = await assignBett(assignOpen.bett.id, patientId);
            setBetten((l) => l.map((b) => (b.id === updated.id ? updated : b)));
            await refreshPatients();
            toast.success("Patient zugewiesen");
            setAssignOpen({ open: false, bett: null });
        } catch (e) {
            toast.error(e?.response?.data?.detail || "Zuweisung fehlgeschlagen");
        }
    };

    const handleRelease = async (bett) => {
        try {
            const updated = await releaseBett(bett.id);
            setBetten((l) => l.map((b) => (b.id === updated.id ? updated : b)));
            await refreshPatients();
            toast.success("Bett freigegeben");
        } catch (e) {
            toast.error("Freigabe fehlgeschlagen");
        }
    };

    const handleLock = async (bett) => {
        try {
            const updated = await updateBett(bett.id, { status: "gesperrt" });
            setBetten((l) => l.map((b) => (b.id === updated.id ? updated : b)));
        } catch (e) {
            toast.error("Sperren fehlgeschlagen");
        }
    };

    const handleUnlock = async (bett) => {
        try {
            const updated = await updateBett(bett.id, { status: "frei" });
            setBetten((l) => l.map((b) => (b.id === updated.id ? updated : b)));
        } catch (e) {
            toast.error("Entsperren fehlgeschlagen");
        }
    };

    const handleDelete = async () => {
        if (!confirmDelete) return;
        try {
            await deleteBett(confirmDelete.id);
            setBetten((l) => l.filter((b) => b.id !== confirmDelete.id));
            toast.success("Bett geloescht");
        } catch (e) {
            toast.error(e?.response?.data?.detail || "Loeschen nicht moeglich");
        } finally {
            setConfirmDelete(null);
        }
    };

    if (!activeIncident) {
        return (
            <div className="mx-auto w-full max-w-xl px-6 py-16">
                <div className="els-surface flex flex-col items-center gap-3 py-14 px-6 text-center" data-testid="betten-no-incident">
                    <Bed className="h-8 w-8 text-primary" />
                    <h3 className="text-heading">Kein aktiver Incident</h3>
                    <Button size="sm" onClick={() => navigate("/")}>
                        <ArrowLeft className="h-3.5 w-3.5" />
                        Zu den Incidents
                    </Button>
                </div>
            </div>
        );
    }

    const canCreate = can("bett.create");
    const canUpdate = can("bett.update");
    const canDelete = can("bett.delete");
    const canAssign = can("bett.assign_patient");
    const canLock = can("bett.update");

    return (
        <div className="mx-auto w-full max-w-[1400px] px-6 py-6">
            {/* Kopf */}
            <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
                <div>
                    <div className="text-caption uppercase tracking-wider text-muted-foreground">
                        Schritt 11 · UHS / Behandlungsplaetze
                    </div>
                    <h1 className="mt-1 text-display" data-testid="betten-title">
                        Behandlungsplaetze
                    </h1>
                    <p className="mt-1 max-w-2xl text-body text-muted-foreground">
                        Verwaltung aller Betten, Liegen und Sitzplaetze im UHS. Patienten zuweisen, Status setzen, Abschnitte gruppieren.
                    </p>
                </div>
                <div className="flex flex-wrap gap-2">
                    {canCreate && (
                        <Button
                            variant="outline"
                            onClick={() => setBulkOpen(true)}
                            data-testid="bulk-open"
                        >
                            <Bolt className="h-4 w-4" />
                            Schnell-Setup
                        </Button>
                    )}
                    {canCreate && (
                        <Button
                            onClick={() => setBettDialog({ open: true, initial: null })}
                            data-testid="bett-new-btn"
                        >
                            <Plus className="h-4 w-4" />
                            Bett anlegen
                        </Button>
                    )}
                </div>
            </div>

            {/* Filter */}
            <div className="mb-4 flex flex-wrap items-center gap-2 rounded-md border border-border bg-surface-sunken px-3 py-2">
                <FilterChip active={filter === "alle"} count={counts.alle} onToggle={() => setFilter("alle")} data-testid="filter-alle">
                    Alle
                </FilterChip>
                <FilterChip active={filter === "frei"} tone="green" count={counts.frei} onToggle={() => setFilter("frei")} data-testid="filter-frei">
                    Frei
                </FilterChip>
                <FilterChip active={filter === "belegt"} tone="red" count={counts.belegt} onToggle={() => setFilter("belegt")} data-testid="filter-belegt">
                    Belegt
                </FilterChip>
                <FilterChip active={filter === "gesperrt"} tone="gray" count={counts.gesperrt} onToggle={() => setFilter("gesperrt")} data-testid="filter-gesperrt">
                    Gesperrt
                </FilterChip>
                <div className="mx-2 h-5 w-px bg-border" />
                {abschnitte.map((a) => (
                    <FilterChip
                        key={a.id}
                        active={filter === `ab-${a.id}`}
                        onToggle={() => setFilter(`ab-${a.id}`)}
                        data-testid={`filter-ab-${a.id}`}
                    >
                        <span className={cn("h-1.5 w-1.5 rounded-full mr-1", getFarbe(a.farbe).dot)} />
                        {a.name}
                    </FilterChip>
                ))}
                <FilterChip
                    active={filter === "ohne-abschnitt"}
                    onToggle={() => setFilter("ohne-abschnitt")}
                    data-testid="filter-ohne-abschnitt"
                >
                    Ohne Abschnitt
                </FilterChip>
            </div>

            {/* Grid */}
            {loading ? (
                <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
                    {Array.from({ length: 8 }).map((_, i) => (
                        <div key={i} className="els-surface h-40 animate-pulse bg-surface-raised/60" />
                    ))}
                </div>
            ) : filtered.length === 0 ? (
                <div className="els-surface p-10 text-center" data-testid="betten-empty">
                    <Bed className="mx-auto h-10 w-10 text-muted-foreground" />
                    <h3 className="mt-3 text-heading">
                        {filter === "alle" ? "Keine Betten angelegt" : "Keine Treffer"}
                    </h3>
                    {filter === "alle" && canCreate && (
                        <Button
                            className="mt-4"
                            onClick={() => setBulkOpen(true)}
                            data-testid="betten-empty-new"
                        >
                            <Bolt className="h-4 w-4" />
                            Schnell-Setup
                        </Button>
                    )}
                </div>
            ) : (
                <div
                    className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4"
                    data-testid="betten-grid"
                >
                    {filtered.map((b) => (
                        <BettKachel
                            key={b.id}
                            bett={b}
                            patient={b.patient_id ? patientById.get(b.patient_id) : null}
                            abschnitt={b.abschnitt_id ? abschnittById.get(b.abschnitt_id) : null}
                            onAssignClick={(x) => setAssignOpen({ open: true, bett: x })}
                            onRelease={handleRelease}
                            onLock={handleLock}
                            onUnlock={handleUnlock}
                            onDelete={(x) => setConfirmDelete(x)}
                            onEdit={(x) => setBettDialog({ open: true, initial: x })}
                            canAssign={canAssign}
                            canEdit={canUpdate}
                            canDelete={canDelete}
                            canLock={canLock}
                        />
                    ))}
                </div>
            )}

            <BettDialog
                open={bettDialog.open}
                onOpenChange={(v) => setBettDialog((d) => ({ ...d, open: v }))}
                initial={bettDialog.initial}
                abschnitte={abschnitte}
                onSave={handleSave}
            />
            <BulkDialog
                open={bulkOpen}
                onOpenChange={setBulkOpen}
                abschnitte={abschnitte}
                onBulk={handleBulk}
            />
            <AssignPatientDialog
                open={assignOpen.open}
                onOpenChange={(v) => setAssignOpen({ open: v, bett: v ? assignOpen.bett : null })}
                patients={patients}
                onAssign={handleAssignPatient}
            />
            <ConfirmModal
                open={!!confirmDelete}
                onOpenChange={(v) => !v && setConfirmDelete(null)}
                title="Bett loeschen?"
                description={confirmDelete ? `"${confirmDelete.name}" wird geloescht.` : ""}
                confirmLabel="Loeschen"
                tone="destructive"
                onConfirm={handleDelete}
            />
        </div>
    );
}
