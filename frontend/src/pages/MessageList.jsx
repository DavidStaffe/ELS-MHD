import * as React from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
    Dialog, DialogContent, DialogDescription, DialogFooter,
    DialogHeader, DialogTitle
} from "@/components/ui/dialog";
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue
} from "@/components/ui/select";
import {
    FilterChip, StatusBadge, KpiTile, ConfirmModal, SectionCard
} from "@/components/primitives";
import { useOps } from "@/context/OpsContext";
import { useIncidents } from "@/context/IncidentContext";
import {
    MESSAGE_PRIO, MESSAGE_KAT, PRIO_KEYS, KAT_KEYS
} from "@/lib/ops-meta";
import { formatDateTime } from "@/lib/time";
import { cn } from "@/lib/utils";
import {
    ArrowLeft, Radio, Plus, Check, Trash2, RefreshCw, AlertTriangle
} from "lucide-react";

function MessageCard({ message, onAck, onDelete }) {
    const prio = MESSAGE_PRIO[message.prioritaet] || MESSAGE_PRIO.normal;
    const kat = MESSAGE_KAT[message.kategorie] || { label: message.kategorie };
    const acknowledged = Boolean(message.quittiert_at);
    return (
        <article
            data-testid={`message-card-${message.id}`}
            data-prio={message.prioritaet}
            className={cn(
                "els-surface relative flex flex-col gap-2 p-3",
                !acknowledged && prio.tone === "red" &&
                    "border-status-red/50 bg-status-red/5",
                !acknowledged && prio.tone === "yellow" &&
                    "border-status-yellow/40 bg-status-yellow/5",
                acknowledged && "opacity-70"
            )}
        >
            {!acknowledged && prio.tone === "red" && (
                <span
                    aria-hidden
                    className="absolute left-0 top-0 h-full w-1 bg-status-red"
                />
            )}
            <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2 flex-wrap">
                    <StatusBadge
                        tone={prio.tone}
                        variant={acknowledged ? "soft" : "solid"}
                        size="sm"
                    >
                        {prio.label}
                    </StatusBadge>
                    <StatusBadge tone="neutral" variant="outline" size="sm">
                        {kat.label}
                    </StatusBadge>
                    {message.von && (
                        <span className="text-caption text-muted-foreground">
                            von <span className="font-medium text-foreground">{message.von}</span>
                        </span>
                    )}
                </div>
                <span className="font-mono text-caption text-muted-foreground whitespace-nowrap">
                    {formatDateTime(message.created_at)}
                </span>
            </div>
            <p className="text-body">{message.text}</p>
            <div className="flex items-center justify-between gap-3 pt-1">
                <div>
                    {acknowledged ? (
                        <span className="text-caption text-muted-foreground">
                            Quittiert · {message.quittiert_von} ·{" "}
                            {formatDateTime(message.quittiert_at)}
                        </span>
                    ) : (
                        <span className="text-caption text-muted-foreground">
                            offen
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-1">
                    {!acknowledged && (
                        <Button
                            size="sm"
                            onClick={() => onAck(message)}
                            data-testid={`message-ack-${message.id}`}
                        >
                            <Check className="h-3.5 w-3.5" />
                            Quittieren
                        </Button>
                    )}
                    <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7"
                        onClick={() => onDelete(message)}
                        data-testid={`message-delete-${message.id}`}
                    >
                        <Trash2 className="h-3.5 w-3.5 text-muted-foreground hover:text-destructive" />
                    </Button>
                </div>
            </div>
        </article>
    );
}

function NewMessageDialog({ open, onOpenChange, onCreate }) {
    const [text, setText] = React.useState("");
    const [prio, setPrio] = React.useState("normal");
    const [kat, setKat] = React.useState("info");
    const [von, setVon] = React.useState("");
    const [submitting, setSubmitting] = React.useState(false);
    const [error, setError] = React.useState(null);

    React.useEffect(() => {
        if (!open) return;
        setText(""); setPrio("normal"); setKat("info"); setVon(""); setError(null);
    }, [open]);

    const submit = async (e) => {
        e.preventDefault();
        if (!text.trim()) return;
        setSubmitting(true); setError(null);
        try {
            await onCreate({ text: text.trim(), prioritaet: prio, kategorie: kat, von: von.trim() });
            onOpenChange?.(false);
        } catch (err) {
            setError(err?.response?.data?.detail || err?.message || "Fehler");
        } finally { setSubmitting(false); }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-lg bg-card border-border" data-testid="new-message-dialog">
                <DialogHeader>
                    <DialogTitle className="text-heading">Neue Meldung</DialogTitle>
                    <DialogDescription className="text-body text-muted-foreground">
                        Kritisch erscheint rot hervorgehoben und triggert einen Konflikt.
                    </DialogDescription>
                </DialogHeader>
                <form onSubmit={submit} className="space-y-4">
                    <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1">
                            <Label>Prioritaet</Label>
                            <Select value={prio} onValueChange={setPrio}>
                                <SelectTrigger data-testid="nm-prio"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                    {PRIO_KEYS.map(k => (
                                        <SelectItem key={k} value={k}>{MESSAGE_PRIO[k].label}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="space-y-1">
                            <Label>Kategorie</Label>
                            <Select value={kat} onValueChange={setKat}>
                                <SelectTrigger data-testid="nm-kat"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                    {KAT_KEYS.map(k => (
                                        <SelectItem key={k} value={k}>{MESSAGE_KAT[k].label}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    </div>
                    <div className="space-y-1">
                        <Label htmlFor="nm-von">Von (optional)</Label>
                        <Input id="nm-von" value={von} onChange={e => setVon(e.target.value)} placeholder="z.B. SAN 2" data-testid="nm-von" />
                    </div>
                    <div className="space-y-1">
                        <Label htmlFor="nm-text">Meldung</Label>
                        <Textarea id="nm-text" value={text} onChange={e => setText(e.target.value)} rows={4} autoFocus data-testid="nm-text" placeholder="Kurz und praezise …" />
                    </div>
                    {error && <div className="rounded-md border border-status-red/40 bg-status-red/10 px-3 py-2 text-caption text-status-red">{error}</div>}
                    <DialogFooter className="gap-2">
                        <Button type="button" variant="outline" onClick={() => onOpenChange?.(false)} disabled={submitting} data-testid="nm-cancel">Abbrechen</Button>
                        <Button type="submit" disabled={submitting || !text.trim()} data-testid="nm-submit">
                            {submitting ? "Senden…" : "Senden"}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}

export default function MessageList() {
    const navigate = useNavigate();
    const { activeIncident } = useIncidents();
    const { messages, refreshMessages, addMessage, ackMsg, rmMessage } = useOps();

    const [newOpen, setNewOpen] = React.useState(false);
    const [deleteCandidate, setDeleteCandidate] = React.useState(null);
    const [filter, setFilter] = React.useState("alle"); // alle / offen / kritisch

    const filtered = React.useMemo(() => {
        let list = messages;
        if (filter === "offen") list = list.filter(m => !m.quittiert_at);
        if (filter === "kritisch") list = list.filter(m => m.prioritaet === "kritisch");
        return list.slice().sort((a, b) => {
            const ao = a.quittiert_at ? 1 : 0;
            const bo = b.quittiert_at ? 1 : 0;
            if (ao !== bo) return ao - bo;
            const ap = MESSAGE_PRIO[a.prioritaet]?.order ?? 9;
            const bp = MESSAGE_PRIO[b.prioritaet]?.order ?? 9;
            if (ap !== bp) return ap - bp;
            return new Date(b.created_at) - new Date(a.created_at);
        });
    }, [messages, filter]);

    const kpis = React.useMemo(() => {
        const k = { total: messages.length, offen: 0, kritisch: 0, dringend: 0 };
        for (const m of messages) {
            if (!m.quittiert_at) k.offen++;
            if (m.prioritaet === "kritisch") k.kritisch++;
            if (m.prioritaet === "dringend") k.dringend++;
        }
        return k;
    }, [messages]);

    if (!activeIncident) {
        return (
            <div className="mx-auto max-w-xl p-6">
                <div className="els-surface p-6 text-center" data-testid="messages-no-incident">
                    <h2 className="text-display">Kein Incident aktiv</h2>
                    <Button className="mt-4" onClick={() => navigate("/")}>
                        <ArrowLeft className="h-4 w-4" />Incident-Uebersicht
                    </Button>
                </div>
            </div>
        );
    }

    return (
        <div className="mx-auto w-full max-w-[1200px] px-6 py-6">
            <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
                <div>
                    <div className="text-caption uppercase tracking-wider text-muted-foreground">
                        Schritt 06 · Kommunikation
                    </div>
                    <h1 className="mt-1 text-display" data-testid="messages-title">
                        Meldungen
                    </h1>
                    <p className="text-caption text-muted-foreground">
                        {activeIncident.name}
                    </p>
                </div>
                <div className="flex gap-2">
                    <Button variant="ghost" size="sm" onClick={refreshMessages} data-testid="messages-refresh">
                        <RefreshCw className="h-4 w-4" />Aktualisieren
                    </Button>
                    <Button onClick={() => setNewOpen(true)} data-testid="messages-new">
                        <Plus className="h-4 w-4" />Neue Meldung
                    </Button>
                </div>
            </div>

            <div className="mb-4 grid grid-cols-2 gap-2 md:grid-cols-4">
                <KpiTile label="Gesamt" value={kpis.total} tone="default" testId="kpi-msg-total" />
                <KpiTile label="Offen" value={kpis.offen} tone="yellow" testId="kpi-msg-offen" />
                <KpiTile label="Kritisch" value={kpis.kritisch} tone="red" testId="kpi-msg-kritisch" />
                <KpiTile label="Dringend" value={kpis.dringend} tone="yellow" testId="kpi-msg-dringend" />
            </div>

            <div className="mb-3 flex flex-wrap items-center gap-2 rounded-md border border-border bg-surface-sunken px-3 py-2">
                <span className="text-caption text-muted-foreground mr-1">Filter:</span>
                <FilterChip active={filter === "alle"} onToggle={() => setFilter("alle")} data-testid="mfilter-alle">Alle</FilterChip>
                <FilterChip active={filter === "offen"} onToggle={() => setFilter("offen")} data-testid="mfilter-offen" count={kpis.offen}>Offen</FilterChip>
                <FilterChip tone="red" active={filter === "kritisch"} onToggle={() => setFilter("kritisch")} data-testid="mfilter-kritisch" count={kpis.kritisch}>Kritisch</FilterChip>
            </div>

            {filtered.length === 0 ? (
                <SectionCard testId="messages-empty">
                    <div className="py-8 text-center text-caption text-muted-foreground">
                        Keine Meldungen. Neue Meldung anlegen &rarr; Button oben.
                    </div>
                </SectionCard>
            ) : (
                <div className="flex flex-col gap-2">
                    {filtered.map(m => (
                        <MessageCard
                            key={m.id}
                            message={m}
                            onAck={(x) => ackMsg(x.id)}
                            onDelete={(x) => setDeleteCandidate(x)}
                        />
                    ))}
                </div>
            )}

            <NewMessageDialog
                open={newOpen}
                onOpenChange={setNewOpen}
                onCreate={async (p) => { await addMessage(p); }}
            />
            <ConfirmModal
                open={deleteCandidate !== null}
                onOpenChange={(v) => !v && setDeleteCandidate(null)}
                title="Meldung loeschen?"
                description={deleteCandidate?.text?.slice(0, 120)}
                confirmLabel="Loeschen"
                tone="destructive"
                onConfirm={() => {
                    if (deleteCandidate) rmMessage(deleteCandidate.id);
                    setDeleteCandidate(null);
                }}
            />
        </div>
    );
}
