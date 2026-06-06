import * as React from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/components/ui/select';
import { listKeywords, createKeyword, updateKeyword, deleteKeyword } from '@/lib/api';
import { SICHTUNG } from '@/lib/patient-meta';
import { toast } from 'sonner';
import { Settings, Plus, Edit2, Trash2 } from 'lucide-react';
import { ConfirmModal } from '@/components/primitives';

export default function KeywordsPage() {
  const [keywords, setKeywords] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [dialogOpen, setDialogOpen] = React.useState(false);
  const [editItem, setEditItem] = React.useState(null);
  const [confirmDelete, setConfirmDelete] = React.useState(null);

  const fetchKeywords = async () => {
    setLoading(true);
    try {
      const data = await listKeywords();
      setKeywords(data);
    } catch (e) {
      toast.error('Fehler beim Laden der Stichwörter');
    } finally {
      setLoading(false);
    }
  };

  React.useEffect(() => {
    fetchKeywords();
  }, []);

  const handleDelete = async (id) => {
    try {
      await deleteKeyword(id);
      toast.success('Stichwort gelöscht');
      fetchKeywords();
      setConfirmDelete(null);
    } catch (e) {
      toast.error('Fehler beim Löschen');
    }
  };

  const handleSave = async (payload) => {
    try {
      if (editItem) {
        await updateKeyword(editItem.id, payload);
        toast.success('Stichwort aktualisiert');
      } else {
        await createKeyword(payload);
        toast.success('Stichwort angelegt');
      }
      setDialogOpen(false);
      fetchKeywords();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Fehler beim Speichern');
    }
  };

  return (
    <div className="mx-auto w-full max-w-[1000px] px-6 py-6">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="text-caption uppercase tracking-wider text-muted-foreground">
            Einstellungen
          </div>
          <h1 className="mt-1 text-display flex items-center gap-2">
            <Settings className="h-6 w-6 text-primary" />
            Stichwort-Katalog
          </h1>
          <p className="mt-1 max-w-2xl text-body text-muted-foreground">
            Verwaltung globaler Stichwörter.
          </p>
        </div>
        <Button onClick={() => { setEditItem(null); setDialogOpen(true); }}>
          <Plus className="mr-2 h-4 w-4" /> Neues Stichwort
        </Button>
      </div>

      <div className="rounded-md border border-border bg-surface shadow-sm">
        {loading ? (
          <div className="p-10 text-center text-muted-foreground animate-pulse">Lade...</div>
        ) : keywords.length === 0 ? (
          <div className="p-10 text-center text-muted-foreground">
            Keine Stichwörter gefunden.
          </div>
        ) : (
          <div className="divide-y divide-border">
            {keywords.map((kw) => (
              <div key={kw.id} className="flex items-center justify-between p-4 hover:bg-surface-raised transition-colors">
                <div>
                  <div className="font-semibold text-heading flex items-center gap-2">
                    {kw.name}
                    {!kw.active && <span className="text-xs bg-status-gray text-status-gray-fg px-2 rounded-full">Inaktiv</span>}
                  </div>
                  {kw.description && <div className="text-sm text-muted-foreground mt-1">{kw.description}</div>}
                  {kw.default_triage_category && (
                    <div className="text-xs mt-1 bg-surface-sunken px-2 py-0.5 rounded border border-border w-max">
                      Auto-Sichtung: <span className="font-mono font-bold">{kw.default_triage_category}</span>
                    </div>
                  )}
                </div>
                <div className="flex gap-2">
                  <Button variant="ghost" size="icon" onClick={() => { setEditItem(kw); setDialogOpen(true); }}>
                    <Edit2 className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="icon" className="text-status-red hover:text-status-red hover:bg-status-red/10" onClick={() => setConfirmDelete(kw)}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <KeywordDialog open={dialogOpen} onOpenChange={setDialogOpen} initial={editItem} onSave={handleSave} />

      <ConfirmModal
        open={Boolean(confirmDelete)}
        onOpenChange={(v) => !v && setConfirmDelete(null)}
        title="Stichwort löschen?"
        description={`Soll das Stichwort "${confirmDelete?.name}" wirklich gelöscht werden? Dies kann nicht rückgängig gemacht werden.`}
        confirmText="Löschen"
        confirmVariant="destructive"
        onConfirm={() => handleDelete(confirmDelete.id)}
      />
    </div>
  );
}

function KeywordDialog({ open, onOpenChange, initial, onSave }) {
  const [form, setForm] = React.useState({ name: '', active: true, description: '', default_triage_category: 'none', sort_order: 0 });
  const [submitting, setSubmitting] = React.useState(false);

  React.useEffect(() => {
    if (open) {
      setForm({
        name: initial?.name || '',
        active: initial?.active ?? true,
        description: initial?.description || '',
        default_triage_category: initial?.default_triage_category || 'none',
        sort_order: initial?.sort_order || 0
      });
    }
  }, [open, initial]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    const payload = {
      name: form.name.trim(),
      active: form.active,
      description: form.description.trim() || null,
      default_triage_category: form.default_triage_category === 'none' ? null : form.default_triage_category,
      sort_order: parseInt(form.sort_order, 10) || 0
    };
    await onSave(payload);
    setSubmitting(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{initial ? 'Stichwort bearbeiten' : 'Neues Stichwort'}</DialogTitle>
          <DialogDescription>Globales Stichwort für alle Einsätze.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label>Name *</Label>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required autoFocus />
          </div>
          <div className="flex items-center space-x-2 border rounded-md p-3">
            <Switch checked={form.active} onCheckedChange={(v) => setForm({ ...form, active: v })} />
            <Label>Aktiv</Label>
          </div>
          <div>
            <Label>Beschreibung (optional)</Label>
            <Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </div>
          <div>
            <Label>Standard-Sichtungskategorie (optional)</Label>
            <Select value={form.default_triage_category} onValueChange={(v) => setForm({ ...form, default_triage_category: v })}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Keine Vorauswahl</SelectItem>
                {SICHTUNG.map(s => <SelectItem key={s.key} value={s.key}>{s.key}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Abbrechen</Button>
            <Button type="submit" disabled={submitting || !form.name.trim()}>Speichern</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
