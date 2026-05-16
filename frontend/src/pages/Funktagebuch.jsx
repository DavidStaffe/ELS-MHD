import * as React from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
    Dialog, DialogContent, DialogDescription, DialogFooter,
    DialogHeader, DialogTitle
} from "@/components/ui/dialog";
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue
} from "@/components/ui/select";
import { FilterChip, StatusBadge, KpiTile, ConfirmModal } from "@/components/primitives";
import { FmsHistory } from "@/components/map/FmsHistory";
import { ChevronDown, ChevronUp } from "lucide-react";
import { useIncidents } from "@/context/IncidentContext";
import { useRole } from "@/context/RoleContext";
import {
    listMessages, createMessage, updateMessage,
    ackMessage, confirmMessage, finalizeMessage, deleteMessage,
    listAbschnitte
} from "@/lib/api";
import { FUNK_TYPEN, FUNK_TYP_KEYS, FUNK_PRIO, fmtTime, fmtDateTime } from "@/lib/funk-meta";
import { getFarbe } from "@/lib/abschnitt-meta";
import { cn } from "@/lib/utils";
import {
    Radio, Plus, Search, Printer, ArrowLeft, Filter, RefreshCw,
    Check, Lock, Trash2, Edit3, Shield, Cpu, User, ChevronRight,
    MapPin, ClipboardList, CheckCircle, AlertOctagon, Send, RadioTower,
    AlertTriangle, X
} from "lucide-react";
import { toast } from "sonner";

const ICON_MAP = {
    funk_ein: RadioTower,
    funk_aus: Send,
    lage: MapPin,
    auftrag: ClipboardList,
    rueckmeldung: CheckCircle,
    vorkommnis: AlertOctagon,
    system: Cpu
};

/* ===================================================================== */
/* Card                                                                  */
/* ===================================================================== */

function EntryCard({ entry, abschnitt, onOpen, onAck, onConfirm, onFinalize, onDelete,
                    canAck, canConfirm, canFinalize, canDelete }) {
    const Icon = ICON_MAP[entry.funk_typ] || Radio;
    const prio = FUNK_PRIO[entry.prioritaet] || FUNK_PRIO.normal;
    const typMeta = FUNK_TYPEN[entry.funk_typ] || FUNK_TYPEN.lage;
    const isSystem = entry.quelle === "system";
    const farbe = abschnitt ? getFarbe(abschnitt.farbe) : null;

    return (
        <article
            data-testid={`entry-card-${entry.id}`}
            data-funk-typ={entry.funk_typ}
            className={cn(
                "els-surface relative flex items-start gap-3 p-3 transition-colors",
                isSystem && "bg-surface-sunken/50 border-dashed",
                !isSystem && prio.tone === "red" && !entry.quittiert_at &&
                    "border-status-red/50 bg-status-red/5",
                !isSystem && prio.tone === "yellow" && !entry.quittiert_at &&
                    "border-status-yellow/30 bg-status-yellow/5",
                entry.quittiert_at && "opacity-75"
            )}
        >
            {/* Zeitstempel */}
            <div className="flex flex-col items-center justify-start gap-1 pt-0.5 w-14 shrink-0 text-center">
                <div className="font-mono text-body tabular-nums">{fmtTime(entry.created_at)}</div>
                <StatusBadge
                    tone={isSystem ? "gray" : typMeta.tone}
                    variant="soft"
                    size="sm"
                    className="font-mono text-[0.6rem]"
                >
                    {typMeta.short}
                </StatusBadge>
            </div>

            {/* Icon */}
            <Icon className={cn(
                "h-4 w-4 shrink-0 mt-1",
                isSystem ? "text-muted-foreground" :
                typMeta.tone === "red" ? "text-status-red" :
                typMeta.tone === "yellow" ? "text-status-yellow" :
                typMeta.tone === "green" ? "text-status-green" : "text-primary"
            )} />

            {/* Inhalt */}
            <button
                type="button"
                onClick={() => onOpen(entry)}
                className="flex-1 min-w-0 text-left els-focus-ring rounded"
                data-testid={`entry-open-${entry.id}`}
            >
                <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-caption text-muted-foreground">{typMeta.label}</span>
                    {entry.absender && (
                        <>
                            <span className="text-muted-foreground/60">·</span>
                            <span className="font-medium">{entry.absender}</span>
                        </>
                    )}
                    {entry.empfaenger && (
                        <>
                            <ChevronRight className="h-3 w-3 text-muted-foreground/60" />
                            <span className="font-medium">{entry.empfaenger}</span>
                        </>
                    )}
                    {abschnitt && (
                        <span className={cn("inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[0.65rem]", farbe.soft)}>
                            <span className={cn("h-1.5 w-1.5 rounded-full", farbe.dot)} />
                            {abschnitt.name}
                        </span>
                    )}
                    {isSystem && (
                        <StatusBadge tone="gray" variant="soft" size="sm">SYSTEM</StatusBadge>
                    )}
                    {entry.finalisiert && !isSystem && (
                        <StatusBadge tone="gray" variant="soft" size="sm">
                            <Lock className="h-2.5 w-2.5" />
                            final
                        </StatusBadge>
                    )}
                    {entry.bestaetigt_at && (
                        <StatusBadge tone="info" variant="soft" size="sm">
                            <Shield className="h-2.5 w-2.5" />
                            EL-OK
                        </StatusBadge>
                    )}
                    <StatusBadge tone={prio.tone} variant="soft" size="sm" className="ml-auto">
                        {prio.label}
                    </StatusBadge>
                </div>
                <p className="mt-1 text-body whitespace-pre-wrap break-words">{entry.text}</p>
                {(entry.erfasst_von || entry.erfasst_rolle) && (
                    <div className="mt-1 text-[0.65rem] uppercase tracking-wider text-muted-foreground">
                        erfasst von {entry.erfasst_von || "?"}
                        {entry.erfasst_rolle && ` · ${entry.erfasst_rolle}`}
                    </div>
                )}
            </button>

            {/* Aktionen */}
            <div className="flex flex-col gap-1 shrink-0 no-print">
                {canAck && !entry.quittiert_at && !isSystem && (
                    <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7"
                        onClick={() => onAck(entry)}
                        title="Quittieren"
                        data-testid={`entry-ack-${entry.id}`}
                    >
                        <Check className="h-3.5 w-3.5" />
                    </Button>
                )}
                {canConfirm && !entry.bestaetigt_at && (
                    <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7"
                        onClick={() => onConfirm(entry)}
                        title="Bestaetigen (EL)"
                        data-testid={`entry-confirm-${entry.id}`}
                    >
                        <Shield className="h-3.5 w-3.5" />
                    </Button>
                )}
                {canFinalize && !entry.finalisiert && !isSystem && (
                    <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7"
                        onClick={() => onFinalize(entry)}
                        title="Finalisieren"
                        data-testid={`entry-finalize-${entry.id}`}
                    >
                        <Lock className="h-3.5 w-3.5" />
                    </Button>
                )}
                {canDelete && !entry.finalisiert && !isSystem && (
                    <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7 text-status-red"
                        onClick={() => onDelete(entry)}
                        title="Loeschen"
                        data-testid={`entry-delete-${entry.id}`}
                    >
                        <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                )}
            </div>
        </article>
    );
}

/* ===================================================================== */
/* Entry Dialog (Create/Edit/Detail)                                     */
/* ===================================================================== */

function EntryDialog({ open, onOpenChange, initial, abschnitte, mode, onSave, role }) {
    const [form, setForm] = React.useState({
        funk_typ: "lage",
        prioritaet: "normal",
        kategorie: "info",
        absender: "",
        empfaenger: "",
        abschnitt_id: null,
        text: ""
    });

    React.useEffect(() => {
        if (initial) {
            setForm({
                funk_typ: initial.funk_typ || "lage",
                prioritaet: initial.prioritaet || "normal",
                kategorie: initial.kategorie || "info",
                absender: initial.absender || initial.von || "",
                empfaenger: initial.empfaenger || "",
                abschnitt_id: initial.abschnitt_id || null,
                text: initial.text || ""
            });
        } else {
            setForm({
                funk_typ: "lage",
                prioritaet: "normal",
                kategorie: "info",
                absender: role?.label || "",
                empfaenger: "",
                abschnitt_id: null,
                text: ""
            });
        }
    }, [initial, role, open]);

    const isEdit = mode === "edit";

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-lg" data-testid="entry-dialog">
                <DialogHeader>
                    <DialogTitle>{isEdit ? "Eintrag bearbeiten" : "Neuer Eintrag"}</DialogTitle>
                    <DialogDescription>
                        Funktagebuch-Eintrag. Pflichtfelder: Typ, Absender, Empfaenger, Inhalt.
                    </DialogDescription>
                </DialogHeader>
                <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-2">
                        <div>
                            <label className="text-caption text-muted-foreground">Typ *</label>
                            <Select value={form.funk_typ} onValueChange={(v) => setForm({ ...form, funk_typ: v })}>
                                <SelectTrigger data-testid="entry-typ">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {FUNK_TYP_KEYS.filter((k) => k !== "system").map((k) => (
                                        <SelectItem key={k} value={k}>
                                            {FUNK_TYPEN[k].label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        <div>
                            <label className="text-caption text-muted-foreground">Prioritaet</label>
                            <Select value={form.prioritaet} onValueChange={(v) => setForm({ ...form, prioritaet: v })}>
                                <SelectTrigger data-testid="entry-prio">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="kritisch">Kritisch</SelectItem>
                                    <SelectItem value="dringend">Dringend</SelectItem>
                                    <SelectItem value="normal">Normal</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                        <div>
                            <label className="text-caption text-muted-foreground">Absender *</label>
                            <Input
                                value={form.absender}
                                onChange={(e) => setForm({ ...form, absender: e.target.value })}
                                placeholder="z.B. RTW 1, UHS, EL"
                                data-testid="entry-absender"
                            />
                        </div>
                        <div>
                            <label className="text-caption text-muted-foreground">Empfaenger *</label>
                            <Input
                                value={form.empfaenger}
                                onChange={(e) => setForm({ ...form, empfaenger: e.target.value })}
                                placeholder="z.B. EL, FA, Alle"
                                data-testid="entry-empfaenger"
                            />
                        </div>
                    </div>
                    <div>
                        <label className="text-caption text-muted-foreground">Abschnitt (optional)</label>
                        <Select
                            value={form.abschnitt_id || "none"}
                            onValueChange={(v) => setForm({ ...form, abschnitt_id: v === "none" ? null : v })}
                        >
                            <SelectTrigger data-testid="entry-abschnitt">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="none">(keiner)</SelectItem>
                                {abschnitte.map((a) => (
                                    <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                    <div>
                        <label className="text-caption text-muted-foreground">Kurzinhalt *</label>
                        <Textarea
                            rows={3}
                            value={form.text}
                            onChange={(e) => setForm({ ...form, text: e.target.value })}
                            placeholder="Kurze, praezise Formulierung."
                            data-testid="entry-text"
                        />
                    </div>
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>Abbrechen</Button>
                    <Button
                        onClick={() => {
                            if (!form.text.trim()) { toast.error("Inhalt erforderlich"); return; }
                            if (!form.absender.trim()) { toast.error("Absender erforderlich"); return; }
                            if (!form.empfaenger.trim()) { toast.error("Empfaenger erforderlich"); return; }
                            onSave(form);
                        }}
                        data-testid="entry-save"
                    >
                        {isEdit ? "Speichern" : "Eintragen"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

/* ===================================================================== */
/* Detail Dialog                                                         */
/* ===================================================================== */

function DetailDialog({ entry, abschnitt, onClose, onEdit, canEdit }) {
    if (!entry) return null;
    const typMeta = FUNK_TYPEN[entry.funk_typ] || FUNK_TYPEN.lage;
    return (
        <Dialog open={!!entry} onOpenChange={(v) => !v && onClose()}>
            <DialogContent className="sm:max-w-lg" data-testid="detail-dialog">
                <DialogHeader>
                    <DialogTitle>{typMeta.label}</DialogTitle>
                    <DialogDescription>
                        {fmtDateTime(entry.created_at)}
                    </DialogDescription>
                </DialogHeader>
                <dl className="grid grid-cols-3 gap-y-2 text-body">
                    <dt className="text-muted-foreground">Absender</dt>
                    <dd className="col-span-2">{entry.absender || "–"}</dd>
                    <dt className="text-muted-foreground">Empfaenger</dt>
                    <dd className="col-span-2">{entry.empfaenger || "–"}</dd>
                    <dt className="text-muted-foreground">Prioritaet</dt>
                    <dd className="col-span-2">
                        <StatusBadge
                            tone={FUNK_PRIO[entry.prioritaet]?.tone}
                            variant="soft"
                            size="sm"
                        >
                            {FUNK_PRIO[entry.prioritaet]?.label}
                        </StatusBadge>
                    </dd>
                    {abschnitt && (
                        <>
                            <dt className="text-muted-foreground">Abschnitt</dt>
                            <dd className="col-span-2">{abschnitt.name}</dd>
                        </>
                    )}
                    <dt className="text-muted-foreground">Quelle</dt>
                    <dd className="col-span-2">
                        {entry.quelle === "system" ? "Systemeintrag" : "Manuelle Erfassung"}
                    </dd>
                    <dt className="text-muted-foreground">Erfasst von</dt>
                    <dd className="col-span-2">
                        {entry.erfasst_von || "?"}{entry.erfasst_rolle && ` (${entry.erfasst_rolle})`}
                    </dd>
                    {entry.quittiert_at && (
                        <>
                            <dt className="text-muted-foreground">Quittiert</dt>
                            <dd className="col-span-2">
                                {fmtDateTime(entry.quittiert_at)} von {entry.quittiert_von}
                            </dd>
                        </>
                    )}
                    {entry.bestaetigt_at && (
                        <>
                            <dt className="text-muted-foreground">Bestaetigt (EL)</dt>
                            <dd className="col-span-2">
                                {fmtDateTime(entry.bestaetigt_at)} von {entry.bestaetigt_von}
                            </dd>
                        </>
                    )}
                    {entry.finalisiert && (
                        <>
                            <dt className="text-muted-foreground">Finalisiert</dt>
                            <dd className="col-span-2">
                                {fmtDateTime(entry.finalisiert_at)} von {entry.finalisiert_von}
                            </dd>
                        </>
                    )}
                </dl>
                <div className="rounded-md bg-surface-raised p-3 text-body whitespace-pre-wrap">
                    {entry.text}
                </div>
                <DialogFooter>
                    {canEdit && !entry.finalisiert && entry.quelle !== "system" && (
                        <Button variant="outline" onClick={onEdit} data-testid="detail-edit">
                            <Edit3 className="h-3.5 w-3.5" />
                            Bearbeiten
                        </Button>
                    )}
                    <Button onClick={onClose}>Schliessen</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

/* ===================================================================== */
/* FMS-VERLAUF (vollstaendig)                                            */
/* ===================================================================== */

function FmsHistoryCollapsible({ incidentId }) {
    const [open, setOpen] = React.useState(true);
    if (!incidentId) return null;
    return (
        <section
            className="els-surface p-3"
            data-testid="funk-fms-history"
        >
            <button
                type="button"
                onClick={() => setOpen((v) => !v)}
                data-testid="funk-fms-history-toggle"
                className="flex w-full items-center justify-between gap-2 text-left els-focus-ring rounded-sm"
            >
                <span className="text-caption uppercase tracking-wider text-muted-foreground">
                    FMS-Verlauf (vollstaendig)
                </span>
                {open ? (
                    <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
                ) : (
                    <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                )}
            </button>
            {open && (
                <div className="mt-2">
                    <FmsHistory incidentId={incidentId} limit={500} compact />
                </div>
            )}
        </section>
    );
}

/* ===================================================================== */
/* PAGE                                                                  */
/* ===================================================================== */

export default function Funktagebuch() {
    const navigate = useNavigate();
    const { activeIncident } = useIncidents();
    const { can, roleMeta, userName, displayName } = useRole();

    const [entries, setEntries] = React.useState([]);
    const [abschnitte, setAbschnitte] = React.useState([]);
    const [loading, setLoading] = React.useState(false);
    const [filterTyp, setFilterTyp] = React.useState("alle");
    const [filterPrio, setFilterPrio] = React.useState("alle");
    const [filterQuelle, setFilterQuelle] = React.useState("alle");
    const [filterAbschnitt, setFilterAbschnitt] = React.useState("alle");
    const [search, setSearch] = React.useState("");
    const [dialog, setDialog] = React.useState({ open: false, initial: null, mode: "create" });
    const [detail, setDetail] = React.useState(null);
    const [confirmDelete, setConfirmDelete] = React.useState(null);

    const incidentId = activeIncident?.id;

    const loadAll = React.useCallback(async () => {
        if (!incidentId) return;
        setLoading(true);
        try {
            const [m, a] = await Promise.all([
                listMessages(incidentId),
                listAbschnitte(incidentId)
            ]);
            setEntries(m);
            setAbschnitte(a);
        } catch (e) {
            toast.error("Laden fehlgeschlagen");
        } finally {
            setLoading(false);
        }
    }, [incidentId]);

    React.useEffect(() => { loadAll(); }, [loadAll]);

    const abschnittById = React.useMemo(() => {
        const m = new Map();
        for (const a of abschnitte) m.set(a.id, a);
        return m;
    }, [abschnitte]);

    const filtered = React.useMemo(() => {
        let list = entries;
        if (filterTyp !== "alle") list = list.filter((e) => e.funk_typ === filterTyp);
        if (filterPrio !== "alle") list = list.filter((e) => e.prioritaet === filterPrio);
        if (filterQuelle !== "alle") list = list.filter((e) => (e.quelle || "manuell") === filterQuelle);
        if (filterAbschnitt !== "alle") {
            if (filterAbschnitt === "ohne") list = list.filter((e) => !e.abschnitt_id);
            else list = list.filter((e) => e.abschnitt_id === filterAbschnitt);
        }
        if (search.trim()) {
            const q = search.toLowerCase();
            list = list.filter((e) =>
                (e.text || "").toLowerCase().includes(q) ||
                (e.absender || "").toLowerCase().includes(q) ||
                (e.empfaenger || "").toLowerCase().includes(q)
            );
        }
        return list;
    }, [entries, filterTyp, filterPrio, filterQuelle, filterAbschnitt, search]);

    const counts = React.useMemo(() => ({
        total: entries.length,
        offen: entries.filter((e) => !e.quittiert_at && e.quelle !== "system").length,
        system: entries.filter((e) => e.quelle === "system").length,
        final: entries.filter((e) => e.finalisiert).length,
        kritisch: entries.filter((e) => e.prioritaet === "kritisch").length
    }), [entries]);

    const handleSave = async (form) => {
        try {
            const erfasstVon = userName
                ? `${userName}${roleMeta?.kurz ? ` (${roleMeta.kurz})` : ""}`
                : (roleMeta?.label || "Nutzer");
            const payload = {
                ...form,
                kategorie: "info",  // backward compat
                von: form.absender,
                erfasst_von: erfasstVon,
                erfasst_rolle: roleMeta?.key || ""
            };
            if (dialog.initial?.id) {
                await updateMessage(dialog.initial.id, payload);
                toast.success("Eintrag aktualisiert");
            } else {
                await createMessage(incidentId, payload);
                toast.success("Eintrag erfasst");
            }
            setDialog({ open: false, initial: null, mode: "create" });
            loadAll();
        } catch (e) {
            toast.error(e?.response?.data?.detail || "Speichern fehlgeschlagen");
        }
    };

    const handleAck = async (entry) => {
        try {
            await ackMessage(entry.id, displayName);
            loadAll();
        } catch { toast.error("Quittieren fehlgeschlagen"); }
    };
    const handleConfirm = async (entry) => {
        try {
            await confirmMessage(entry.id, { bestaetigt_von: displayName });
            toast.success("Bestaetigt");
            loadAll();
        } catch { toast.error("Bestaetigen fehlgeschlagen"); }
    };
    const handleFinalize = async (entry) => {
        try {
            await finalizeMessage(entry.id, displayName);
            toast.success("Finalisiert");
            loadAll();
        } catch { toast.error("Finalisieren fehlgeschlagen"); }
    };
    const handleDelete = async () => {
        if (!confirmDelete) return;
        try {
            await deleteMessage(confirmDelete.id);
            toast.success("Eintrag geloescht");
            loadAll();
        } catch (e) {
            toast.error(e?.response?.data?.detail || "Loeschen fehlgeschlagen");
        } finally {
            setConfirmDelete(null);
        }
    };

    if (!activeIncident) {
        return (
            <div className="mx-auto max-w-xl p-6">
                <div className="els-surface p-6 text-center" data-testid="funk-no-incident">
                    <Radio className="mx-auto h-10 w-10 text-primary" />
                    <h2 className="text-heading mt-2">Kein Incident aktiv</h2>
                    <Button className="mt-4" onClick={() => navigate("/")}>
                        <ArrowLeft className="h-4 w-4" />
                        Incident-Uebersicht
                    </Button>
                </div>
            </div>
        );
    }

    return (
        <div className="mx-auto w-full max-w-[1400px] px-6 py-6 no-print">
            {/* Kopf */}
            <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
                <div>
                    <div className="text-caption uppercase tracking-wider text-muted-foreground">
                        Funk & Dokumentation
                    </div>
                    <h1 className="mt-1 text-display" data-testid="funk-title">
                        Funktagebuch
                    </h1>
                    <p className="text-caption text-muted-foreground max-w-2xl">
                        Chronologische Dokumentation des Einsatzverlaufs. Manuelle Eintraege und
                        automatische Systemmeldungen.
                    </p>
                </div>
                <div className="flex flex-wrap gap-2">
                    <Button variant="outline" size="sm" onClick={() => window.print()} data-testid="funk-print">
                        <Printer className="h-3.5 w-3.5" />
                        Drucken / PDF
                    </Button>
                    <Button variant="ghost" size="sm" onClick={loadAll} data-testid="funk-refresh">
                        <RefreshCw className="h-3.5 w-3.5" />
                        Aktualisieren
                    </Button>
                    {can("message.create") && (
                        <Button onClick={() => setDialog({ open: true, initial: null, mode: "create" })}
                                data-testid="funk-new-btn">
                            <Plus className="h-4 w-4" />
                            Eintrag erfassen
                        </Button>
                    )}
                </div>
            </div>

            {/* KPIs */}
            <div className="mb-4 grid grid-cols-2 gap-2 md:grid-cols-5">
                <KpiTile label="Gesamt" value={counts.total} tone="default" testId="kpi-funk-total" />
                <KpiTile label="Offen" value={counts.offen} tone={counts.offen > 0 ? "yellow" : "green"} testId="kpi-funk-offen" />
                <KpiTile label="Kritisch" value={counts.kritisch} tone={counts.kritisch > 0 ? "red" : "green"} testId="kpi-funk-krit" />
                <KpiTile label="Systemeintraege" value={counts.system} tone="default" testId="kpi-funk-sys" />
                <KpiTile label="Finalisiert" value={counts.final} tone="default" testId="kpi-funk-final" />
            </div>

            {/* Filter */}
            <div className="mb-4 els-surface p-3 space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                    <Filter className="h-3.5 w-3.5 text-muted-foreground" />
                    <span className="text-caption uppercase tracking-wider text-muted-foreground">Typ:</span>
                    <FilterChip active={filterTyp === "alle"} onToggle={() => setFilterTyp("alle")} data-testid="f-typ-alle">Alle</FilterChip>
                    {FUNK_TYP_KEYS.map((k) => (
                        <FilterChip
                            key={k}
                            active={filterTyp === k}
                            onToggle={() => setFilterTyp(k)}
                            data-testid={`f-typ-${k}`}
                        >
                            {FUNK_TYPEN[k].label}
                        </FilterChip>
                    ))}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    <span className="text-caption uppercase tracking-wider text-muted-foreground">Prio:</span>
                    <FilterChip active={filterPrio === "alle"} onToggle={() => setFilterPrio("alle")} data-testid="f-prio-alle">Alle</FilterChip>
                    <FilterChip active={filterPrio === "kritisch"} tone="red" onToggle={() => setFilterPrio("kritisch")} data-testid="f-prio-kritisch">Kritisch</FilterChip>
                    <FilterChip active={filterPrio === "dringend"} tone="yellow" onToggle={() => setFilterPrio("dringend")} data-testid="f-prio-dringend">Dringend</FilterChip>
                    <FilterChip active={filterPrio === "normal"} tone="green" onToggle={() => setFilterPrio("normal")} data-testid="f-prio-normal">Normal</FilterChip>
                    <div className="mx-2 h-4 w-px bg-border" />
                    <span className="text-caption uppercase tracking-wider text-muted-foreground">Quelle:</span>
                    <FilterChip active={filterQuelle === "alle"} onToggle={() => setFilterQuelle("alle")} data-testid="f-quelle-alle">Alle</FilterChip>
                    <FilterChip active={filterQuelle === "manuell"} onToggle={() => setFilterQuelle("manuell")} data-testid="f-quelle-manuell">Manuell</FilterChip>
                    <FilterChip active={filterQuelle === "system"} onToggle={() => setFilterQuelle("system")} data-testid="f-quelle-system">System</FilterChip>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    <span className="text-caption uppercase tracking-wider text-muted-foreground">Abschnitt:</span>
                    <FilterChip active={filterAbschnitt === "alle"} onToggle={() => setFilterAbschnitt("alle")} data-testid="f-ab-alle">Alle</FilterChip>
                    {abschnitte.map((a) => (
                        <FilterChip
                            key={a.id}
                            active={filterAbschnitt === a.id}
                            onToggle={() => setFilterAbschnitt(a.id)}
                            data-testid={`f-ab-${a.id}`}
                        >
                            <span className={cn("h-1.5 w-1.5 rounded-full mr-1", getFarbe(a.farbe).dot)} />
                            {a.name}
                        </FilterChip>
                    ))}
                    <FilterChip active={filterAbschnitt === "ohne"} onToggle={() => setFilterAbschnitt("ohne")} data-testid="f-ab-ohne">Ohne</FilterChip>
                </div>
                <div className="flex items-center gap-2">
                    <Search className="h-3.5 w-3.5 text-muted-foreground" />
                    <Input
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="Suche in Text, Absender, Empfaenger …"
                        className="max-w-md bg-background"
                        data-testid="funk-search"
                    />
                    {search && (
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setSearch("")}>
                            <X className="h-3.5 w-3.5" />
                        </Button>
                    )}
                </div>
            </div>

            {/* FMS-Verlauf (vollstaendig) - Quelle der Wahrheit fuer alle FMS-Aenderungen */}
            <FmsHistoryCollapsible incidentId={incidentId} />

            {/* Liste */}
            <div className="print-area">
                <div className="hidden print:block mb-4">
                    <h1 className="text-xl font-bold">Funktagebuch – {activeIncident.name}</h1>
                    <p className="text-sm text-slate-600">
                        Erstellt {fmtDateTime(new Date().toISOString())} · {filtered.length} Eintraege
                    </p>
                </div>
                {loading ? (
                    <div className="space-y-2">
                        {Array.from({ length: 4 }).map((_, i) => (
                            <div key={i} className="els-surface h-16 animate-pulse bg-surface-raised/60" />
                        ))}
                    </div>
                ) : filtered.length === 0 ? (
                    <div className="els-surface p-10 text-center" data-testid="funk-empty">
                        <Radio className="mx-auto h-10 w-10 text-muted-foreground" />
                        <h3 className="mt-3 text-heading">Keine Eintraege</h3>
                        <p className="text-caption text-muted-foreground">
                            {entries.length === 0 ? "Noch keine Eintraege erfasst." : "Kein Eintrag entspricht den Filtern."}
                        </p>
                    </div>
                ) : (
                    <div className="space-y-2" data-testid="funk-list">
                        {filtered.map((e) => (
                            <EntryCard
                                key={e.id}
                                entry={e}
                                abschnitt={e.abschnitt_id ? abschnittById.get(e.abschnitt_id) : null}
                                onOpen={setDetail}
                                onAck={handleAck}
                                onConfirm={handleConfirm}
                                onFinalize={handleFinalize}
                                onDelete={(x) => setConfirmDelete(x)}
                                canAck={can("message.ack")}
                                canConfirm={can("message.confirm")}
                                canFinalize={can("message.finalize")}
                                canDelete={can("message.delete")}
                            />
                        ))}
                    </div>
                )}
            </div>

            <EntryDialog
                open={dialog.open}
                onOpenChange={(v) => setDialog((d) => ({ ...d, open: v }))}
                initial={dialog.initial}
                mode={dialog.mode}
                abschnitte={abschnitte}
                onSave={handleSave}
                role={roleMeta}
            />

            <DetailDialog
                entry={detail}
                abschnitt={detail?.abschnitt_id ? abschnittById.get(detail.abschnitt_id) : null}
                onClose={() => setDetail(null)}
                onEdit={() => {
                    const e = detail;
                    setDetail(null);
                    setDialog({ open: true, initial: e, mode: "edit" });
                }}
                canEdit={can("message.update")}
            />

            <ConfirmModal
                open={!!confirmDelete}
                onOpenChange={(v) => !v && setConfirmDelete(null)}
                title="Eintrag loeschen?"
                description={confirmDelete
                    ? `Eintrag ${fmtTime(confirmDelete.created_at)} wird unwiderruflich geloescht.`
                    : ""}
                confirmLabel="Loeschen"
                tone="destructive"
                onConfirm={handleDelete}
            />
        </div>
    );
}
