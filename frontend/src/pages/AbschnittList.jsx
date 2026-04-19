import * as React from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter
} from "@/components/ui/dialog";
import { StatusBadge, ConfirmModal } from "@/components/primitives";
import { useIncidents } from "@/context/IncidentContext";
import { useRole } from "@/context/RoleContext";
import {
    listAbschnitte,
    createAbschnitt,
    updateAbschnitt,
    deleteAbschnitt,
    listResources,
    listBetten,
    updateResource
} from "@/lib/api";
import { ABSCHNITT_FARBEN, getFarbe } from "@/lib/abschnitt-meta";
import { cn } from "@/lib/utils";
import {
    Plus,
    Layers,
    Edit3,
    Trash2,
    Power,
    PowerOff,
    Boxes,
    Bed,
    CheckCircle2,
    AlertTriangle,
    Activity,
    ArrowLeft,
    UserPlus,
    UserMinus
} from "lucide-react";
import { toast } from "sonner";

const EMPTY_FORM = { name: "", farbe: "blue", beschreibung: "", aktiv: true };

function AbschnittDialog({ open, onOpenChange, initial, onSave }) {
    const [form, setForm] = React.useState(EMPTY_FORM);
    React.useEffect(() => {
        setForm(initial || EMPTY_FORM);
    }, [initial, open]);
    const isEdit = Boolean(initial?.id);

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md" data-testid="abschnitt-dialog">
                <DialogHeader>
                    <DialogTitle>{isEdit ? "Abschnitt bearbeiten" : "Neuer Abschnitt"}</DialogTitle>
                    <DialogDescription>
                        Einsatzabschnitte gruppieren Ressourcen und Betten visuell.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-3">
                    <div>
                        <label className="text-caption text-muted-foreground">Name</label>
                        <Input
                            value={form.name}
                            onChange={(e) => setForm({ ...form, name: e.target.value })}
                            placeholder="z.B. Abschnitt Nord, BHP, Zelt A"
                            data-testid="abschnitt-name-input"
                        />
                    </div>
                    <div>
                        <label className="text-caption text-muted-foreground">Farbe</label>
                        <div className="mt-1 flex flex-wrap gap-2">
                            {ABSCHNITT_FARBEN.map((f) => (
                                <button
                                    key={f.key}
                                    type="button"
                                    onClick={() => setForm({ ...form, farbe: f.key })}
                                    data-testid={`abschnitt-farbe-${f.key}`}
                                    className={cn(
                                        "h-7 w-7 rounded-full border-2 transition-transform els-focus-ring",
                                        f.chipBg,
                                        form.farbe === f.key
                                            ? "border-foreground scale-110"
                                            : "border-transparent opacity-70 hover:opacity-100"
                                    )}
                                    title={f.label}
                                />
                            ))}
                        </div>
                    </div>
                    <div>
                        <label className="text-caption text-muted-foreground">Beschreibung (optional)</label>
                        <Textarea
                            value={form.beschreibung}
                            onChange={(e) => setForm({ ...form, beschreibung: e.target.value })}
                            rows={2}
                            placeholder="z.B. Hauptbuehne, Eingang Nord"
                            data-testid="abschnitt-beschreibung"
                        />
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
                        data-testid="abschnitt-save"
                    >
                        {isEdit ? "Speichern" : "Anlegen"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

function KachelAmpel({ ampel }) {
    if (ampel === "red") return <StatusBadge tone="red" variant="soft" size="sm">Voll im Einsatz</StatusBadge>;
    if (ampel === "yellow") return <StatusBadge tone="yellow" variant="soft" size="sm">Teilweise</StatusBadge>;
    if (ampel === "green") return <StatusBadge tone="green" variant="soft" size="sm">Bereit</StatusBadge>;
    return <StatusBadge tone="gray" variant="soft" size="sm">Leer</StatusBadge>;
}

function AbschnittKachel({ abschnitt, kpi, onOpen, onEdit, onDelete, onToggleAktiv, canEdit, canDelete }) {
    const farbe = getFarbe(abschnitt.farbe);
    return (
        <div
            className={cn(
                "els-surface relative overflow-hidden transition-colors",
                !abschnitt.aktiv && "opacity-60"
            )}
            data-testid={`abschnitt-kachel-${abschnitt.id}`}
        >
            <span aria-hidden className={cn("absolute left-0 top-0 h-full w-1.5", farbe.chipBg)} />
            <div className="p-4 pl-5">
                <div className="flex items-start justify-between gap-2">
                    <button
                        type="button"
                        onClick={() => onOpen(abschnitt)}
                        className="flex-1 text-left els-focus-ring"
                        data-testid={`abschnitt-open-${abschnitt.id}`}
                    >
                        <div className="flex items-center gap-2">
                            <span className={cn("h-2.5 w-2.5 rounded-full", farbe.dot)} />
                            <h3 className="text-heading truncate">{abschnitt.name}</h3>
                            {!abschnitt.aktiv && (
                                <StatusBadge tone="gray" variant="soft" size="sm">inaktiv</StatusBadge>
                            )}
                        </div>
                        {abschnitt.beschreibung && (
                            <p className="mt-1 text-caption text-muted-foreground line-clamp-2">
                                {abschnitt.beschreibung}
                            </p>
                        )}
                    </button>
                    <div className="flex items-center gap-1">
                        {canEdit && (
                            <>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-7 w-7"
                                    onClick={() => onToggleAktiv(abschnitt)}
                                    title={abschnitt.aktiv ? "Deaktivieren" : "Aktivieren"}
                                    data-testid={`abschnitt-toggle-${abschnitt.id}`}
                                >
                                    {abschnitt.aktiv ? (
                                        <PowerOff className="h-3.5 w-3.5" />
                                    ) : (
                                        <Power className="h-3.5 w-3.5" />
                                    )}
                                </Button>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-7 w-7"
                                    onClick={() => onEdit(abschnitt)}
                                    data-testid={`abschnitt-edit-${abschnitt.id}`}
                                    title="Bearbeiten"
                                >
                                    <Edit3 className="h-3.5 w-3.5" />
                                </Button>
                            </>
                        )}
                        {canDelete && (
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7 text-status-red"
                                onClick={() => onDelete(abschnitt)}
                                data-testid={`abschnitt-delete-${abschnitt.id}`}
                                title="Loeschen (nur bei abgeschlossenem Incident)"
                            >
                                <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                        )}
                    </div>
                </div>

                <div className="mt-3 grid grid-cols-3 gap-2 text-caption">
                    <div>
                        <div className="text-muted-foreground flex items-center gap-1">
                            <Boxes className="h-3 w-3" />
                            Ressourcen
                        </div>
                        <div className="font-mono tabular-nums text-body">
                            {kpi.ressourcen_im_einsatz}/{kpi.ressourcen_total}
                        </div>
                    </div>
                    <div>
                        <div className="text-muted-foreground flex items-center gap-1">
                            <Bed className="h-3 w-3" />
                            Betten
                        </div>
                        <div className="font-mono tabular-nums text-body">
                            {kpi.betten_belegt}/{kpi.betten_total}
                        </div>
                    </div>
                    <div className="flex items-end justify-end">
                        <KachelAmpel ampel={kpi.ampel} />
                    </div>
                </div>
            </div>
        </div>
    );
}

function AbschnittDetail({ abschnitt, resources, betten, onClose, onAssignResource, onUnassignResource, canAssign }) {
    if (!abschnitt) return null;
    const farbe = getFarbe(abschnitt.farbe);
    const zugewiesen = resources.filter((r) => r.abschnitt_id === abschnitt.id);
    const unassigned = resources.filter((r) => !r.abschnitt_id);
    const a_betten = betten.filter((b) => b.abschnitt_id === abschnitt.id);

    return (
        <Dialog open={!!abschnitt} onOpenChange={(v) => !v && onClose()}>
            <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-hidden flex flex-col" data-testid="abschnitt-detail">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <span className={cn("h-3 w-3 rounded-full", farbe.dot)} />
                        {abschnitt.name}
                    </DialogTitle>
                    <DialogDescription>
                        {abschnitt.beschreibung || "Detailansicht"}
                    </DialogDescription>
                </DialogHeader>

                <div className="flex-1 overflow-y-auto space-y-4">
                    <section>
                        <div className="flex items-center justify-between mb-2">
                            <h4 className="text-heading">Ressourcen ({zugewiesen.length})</h4>
                        </div>
                        {zugewiesen.length === 0 ? (
                            <div className="text-caption text-muted-foreground py-2">
                                Keine Ressourcen zugewiesen.
                            </div>
                        ) : (
                            <ul className="space-y-1.5">
                                {zugewiesen.map((r) => (
                                    <li
                                        key={r.id}
                                        className="flex items-center gap-2 rounded-md bg-surface-raised px-3 py-1.5"
                                        data-testid={`detail-res-${r.id}`}
                                    >
                                        <Boxes className="h-3.5 w-3.5 text-muted-foreground" />
                                        <span className="flex-1 truncate text-body">{r.name}</span>
                                        <StatusBadge
                                            tone={r.status === "im_einsatz" ? "yellow" : r.status === "verfuegbar" ? "green" : "gray"}
                                            variant="soft"
                                            size="sm"
                                        >
                                            {r.status}
                                        </StatusBadge>
                                        {canAssign && (
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                className="h-6 w-6"
                                                onClick={() => onUnassignResource(r)}
                                                title="Entfernen"
                                                data-testid={`detail-res-unassign-${r.id}`}
                                            >
                                                <UserMinus className="h-3 w-3" />
                                            </Button>
                                        )}
                                    </li>
                                ))}
                            </ul>
                        )}
                    </section>

                    {canAssign && unassigned.length > 0 && (
                        <section>
                            <h4 className="text-heading mb-2">Nicht zugewiesen ({unassigned.length})</h4>
                            <ul className="space-y-1.5">
                                {unassigned.map((r) => (
                                    <li
                                        key={r.id}
                                        className="flex items-center gap-2 rounded-md bg-surface-raised/60 px-3 py-1.5"
                                    >
                                        <Boxes className="h-3.5 w-3.5 text-muted-foreground" />
                                        <span className="flex-1 truncate text-body text-muted-foreground">
                                            {r.name}
                                        </span>
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => onAssignResource(r)}
                                            data-testid={`detail-res-assign-${r.id}`}
                                        >
                                            <UserPlus className="h-3 w-3" />
                                            Zuweisen
                                        </Button>
                                    </li>
                                ))}
                            </ul>
                        </section>
                    )}

                    <section>
                        <h4 className="text-heading mb-2">Betten ({a_betten.length})</h4>
                        {a_betten.length === 0 ? (
                            <div className="text-caption text-muted-foreground py-2">
                                Keine Betten zugeordnet.
                            </div>
                        ) : (
                            <ul className="grid grid-cols-2 gap-2">
                                {a_betten.map((b) => (
                                    <li
                                        key={b.id}
                                        className="flex items-center gap-2 rounded-md bg-surface-raised px-3 py-1.5"
                                    >
                                        <Bed className="h-3.5 w-3.5 text-muted-foreground" />
                                        <span className="flex-1 truncate text-body">{b.name}</span>
                                        <StatusBadge
                                            tone={b.status === "frei" ? "green" : b.status === "belegt" ? "red" : "gray"}
                                            variant="soft"
                                            size="sm"
                                        >
                                            {b.status}
                                        </StatusBadge>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </section>
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={onClose}>
                        Schliessen
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

export default function AbschnittList() {
    const navigate = useNavigate();
    const { activeIncident } = useIncidents();
    const { can } = useRole();

    const [abschnitte, setAbschnitte] = React.useState([]);
    const [resources, setResources] = React.useState([]);
    const [betten, setBetten] = React.useState([]);
    const [loading, setLoading] = React.useState(false);
    const [dialog, setDialog] = React.useState({ open: false, initial: null });
    const [detail, setDetail] = React.useState(null);
    const [confirmDelete, setConfirmDelete] = React.useState(null);

    const incidentId = activeIncident?.id;

    const loadAll = React.useCallback(async () => {
        if (!incidentId) return;
        setLoading(true);
        try {
            const [a, r, b] = await Promise.all([
                listAbschnitte(incidentId),
                listResources(incidentId),
                listBetten(incidentId)
            ]);
            setAbschnitte(a);
            setResources(r);
            setBetten(b);
        } catch (e) {
            toast.error("Laden fehlgeschlagen");
        } finally {
            setLoading(false);
        }
    }, [incidentId]);

    React.useEffect(() => {
        loadAll();
    }, [loadAll]);

    const kpiFor = React.useCallback(
        (a) => {
            const res = resources.filter((r) => r.abschnitt_id === a.id);
            const bet = betten.filter((b) => b.abschnitt_id === a.id);
            const imEinsatz = res.filter((r) => r.status === "im_einsatz").length;
            const belegt = bet.filter((b) => b.status === "belegt").length;
            let ampel;
            if (res.length === 0) ampel = "gray";
            else if (imEinsatz === res.length) ampel = "red";
            else if (imEinsatz > 0) ampel = "yellow";
            else ampel = "green";
            return {
                ressourcen_total: res.length,
                ressourcen_im_einsatz: imEinsatz,
                betten_total: bet.length,
                betten_belegt: belegt,
                ampel
            };
        },
        [resources, betten]
    );

    const handleSave = async (form) => {
        try {
            if (dialog.initial?.id) {
                const updated = await updateAbschnitt(dialog.initial.id, form);
                setAbschnitte((list) => list.map((a) => (a.id === updated.id ? updated : a)));
                toast.success("Abschnitt aktualisiert");
            } else {
                const created = await createAbschnitt(incidentId, form);
                setAbschnitte((list) => [...list, created]);
                toast.success("Abschnitt angelegt");
            }
            setDialog({ open: false, initial: null });
        } catch (e) {
            toast.error("Speichern fehlgeschlagen");
        }
    };

    const handleToggleAktiv = async (a) => {
        try {
            const updated = await updateAbschnitt(a.id, { aktiv: !a.aktiv });
            setAbschnitte((list) => list.map((x) => (x.id === updated.id ? updated : x)));
        } catch (e) {
            toast.error("Aktivierung fehlgeschlagen");
        }
    };

    const handleDelete = async () => {
        if (!confirmDelete) return;
        try {
            await deleteAbschnitt(confirmDelete.id);
            setAbschnitte((list) => list.filter((a) => a.id !== confirmDelete.id));
            toast.success("Abschnitt geloescht");
        } catch (e) {
            toast.error(e?.response?.data?.detail || "Loeschen nicht moeglich");
        } finally {
            setConfirmDelete(null);
        }
    };

    const handleAssignResource = async (resource) => {
        if (!detail) return;
        try {
            const updated = await updateResource(resource.id, { abschnitt_id: detail.id });
            setResources((list) => list.map((r) => (r.id === updated.id ? updated : r)));
            toast.success("Ressource zugewiesen");
        } catch (e) {
            toast.error("Zuweisung fehlgeschlagen");
        }
    };

    const handleUnassignResource = async (resource) => {
        try {
            const updated = await updateResource(resource.id, { abschnitt_id: null });
            setResources((list) => list.map((r) => (r.id === updated.id ? updated : r)));
            toast.success("Ressource entfernt");
        } catch (e) {
            toast.error("Entfernen fehlgeschlagen");
        }
    };

    if (!activeIncident) {
        return (
            <div className="mx-auto w-full max-w-xl px-6 py-16">
                <div className="els-surface flex flex-col items-center gap-3 py-14 px-6 text-center" data-testid="abschnitt-no-incident">
                    <Layers className="h-8 w-8 text-primary" />
                    <h3 className="text-heading">Kein aktiver Incident</h3>
                    <p className="text-caption text-muted-foreground">
                        Waehle oder starte einen Incident, um Einsatzabschnitte zu verwalten.
                    </p>
                    <Button size="sm" onClick={() => navigate("/")}>
                        <ArrowLeft className="h-3.5 w-3.5" />
                        Zu den Incidents
                    </Button>
                </div>
            </div>
        );
    }

    const canCreate = can("abschnitt.create");
    const canUpdate = can("abschnitt.update");
    const canDelete = can("abschnitt.delete") && activeIncident.status === "abgeschlossen";
    const canAssign = can("abschnitt.assign_resource");

    const unassignedResources = resources.filter((r) => !r.abschnitt_id);

    return (
        <div className="mx-auto w-full max-w-[1400px] px-6 py-6">
            {/* Kopf */}
            <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
                <div>
                    <div className="text-caption uppercase tracking-wider text-muted-foreground">
                        Schritt 10 · Einsatzabschnitte
                    </div>
                    <h1 className="mt-1 text-display" data-testid="abschnitte-title">
                        Abschnitte
                    </h1>
                    <p className="mt-1 max-w-2xl text-body text-muted-foreground">
                        Gruppiere Ressourcen und Betten in benannten Teilbereichen (z.B. Abschnitt Nord, BHP, Zelt A).
                    </p>
                </div>
                {canCreate && (
                    <Button
                        onClick={() => setDialog({ open: true, initial: null })}
                        data-testid="abschnitt-new-btn"
                    >
                        <Plus className="h-4 w-4" />
                        Abschnitt anlegen
                    </Button>
                )}
            </div>

            {/* Kacheln */}
            {loading ? (
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                    {Array.from({ length: 3 }).map((_, i) => (
                        <div key={i} className="els-surface h-40 animate-pulse bg-surface-raised/60" />
                    ))}
                </div>
            ) : abschnitte.length === 0 ? (
                <div className="els-surface p-10 text-center" data-testid="abschnitte-empty">
                    <Layers className="mx-auto h-10 w-10 text-muted-foreground" />
                    <h3 className="mt-3 text-heading">Keine Abschnitte angelegt</h3>
                    <p className="mt-1 text-caption text-muted-foreground">
                        Lege den ersten Einsatzabschnitt an.
                    </p>
                    {canCreate && (
                        <Button
                            className="mt-4"
                            onClick={() => setDialog({ open: true, initial: null })}
                            data-testid="abschnitt-empty-new-btn"
                        >
                            <Plus className="h-4 w-4" />
                            Abschnitt anlegen
                        </Button>
                    )}
                </div>
            ) : (
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3" data-testid="abschnitte-grid">
                    {abschnitte.map((a) => (
                        <AbschnittKachel
                            key={a.id}
                            abschnitt={a}
                            kpi={kpiFor(a)}
                            onOpen={setDetail}
                            onEdit={(x) => setDialog({ open: true, initial: x })}
                            onDelete={(x) => setConfirmDelete(x)}
                            onToggleAktiv={handleToggleAktiv}
                            canEdit={canUpdate}
                            canDelete={canDelete}
                        />
                    ))}
                </div>
            )}

            {/* Nicht zugewiesene Ressourcen */}
            {unassignedResources.length > 0 && (
                <div className="mt-6 els-surface p-4" data-testid="unassigned-resources">
                    <div className="flex items-center gap-2 mb-3">
                        <AlertTriangle className="h-4 w-4 text-status-yellow" />
                        <h3 className="text-heading">
                            Nicht zugewiesene Ressourcen ({unassignedResources.length})
                        </h3>
                    </div>
                    <ul className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-1.5">
                        {unassignedResources.map((r) => (
                            <li
                                key={r.id}
                                className="flex items-center gap-2 rounded-md bg-surface-raised px-3 py-1.5 text-caption"
                            >
                                <Boxes className="h-3 w-3 text-muted-foreground" />
                                <span className="flex-1 truncate">{r.name}</span>
                                <StatusBadge tone="gray" variant="soft" size="sm">
                                    {r.status}
                                </StatusBadge>
                            </li>
                        ))}
                    </ul>
                    <p className="mt-2 text-caption text-muted-foreground">
                        Weise Ressourcen einem Abschnitt zu, um sie zu gruppieren (Abschnitt oeffnen → Zuweisen).
                    </p>
                </div>
            )}

            <AbschnittDialog
                open={dialog.open}
                onOpenChange={(v) => setDialog((d) => ({ ...d, open: v }))}
                initial={dialog.initial}
                onSave={handleSave}
            />

            <AbschnittDetail
                abschnitt={detail}
                resources={resources}
                betten={betten}
                onClose={() => setDetail(null)}
                onAssignResource={handleAssignResource}
                onUnassignResource={handleUnassignResource}
                canAssign={canAssign}
            />

            <ConfirmModal
                open={!!confirmDelete}
                onOpenChange={(v) => !v && setConfirmDelete(null)}
                title="Abschnitt loeschen?"
                description={
                    confirmDelete
                        ? `"${confirmDelete.name}" wird geloescht. Ressourcen und Betten werden vom Abschnitt getrennt.`
                        : ""
                }
                confirmLabel="Loeschen"
                tone="destructive"
                onConfirm={handleDelete}
            />
        </div>
    );
}
