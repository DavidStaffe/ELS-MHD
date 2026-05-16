import * as React from 'react';
import { Bell, BellRing, BellOff, Check, Volume2, VolumeX, Clock3, RadioTower, Hand } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { StatusBadge } from '@/components/primitives';
import { useIncidents } from '@/context/IncidentContext';
import { useRole, ROLES } from '@/context/RoleContext';
import { fmsMeta } from '@/lib/fms-status';
import { listFmsEvents, acknowledgeFmsEvent } from '@/lib/api';
import { toast } from 'sonner';

const POLL_INTERVAL_MS = 10000;
const BEEP_INTERVAL_MS = 5000;
const SOUND_KEY = 'els-fms-alert-sound';
const SEEN_KEY = 'els-fms-alert-seen';

/**
 * Spielt einen kurzen FMS-Alert-Beep ueber die Web Audio API ab.
 * Zwei aufeinanderfolgende Toene (kurz-kurz) damit es als "Alarm" wahrgenommen wird.
 */
function playBeep() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    const now = ctx.currentTime;

    const beep = (start, freq) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.0001, now + start);
      gain.gain.exponentialRampToValueAtTime(0.35, now + start + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + start + 0.18);
      osc.connect(gain).connect(ctx.destination);
      osc.start(now + start);
      osc.stop(now + start + 0.2);
    };
    beep(0, 880);
    beep(0.22, 1175);
    // Auto-close context after the second tone played out.
    setTimeout(() => ctx.close().catch(() => {}), 600);
  } catch {
    /* noop – browser tab without user gesture etc. */
  }
}

function fmtTime(iso) {
  if (!iso) return '–';
  try {
    return new Date(iso).toLocaleTimeString('de-DE', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return iso;
  }
}

function fmtFullTime(iso) {
  if (!iso) return '–';
  try {
    return new Date(iso).toLocaleString('de-DE', {
      hour: '2-digit',
      minute: '2-digit',
      day: '2-digit',
      month: '2-digit',
    });
  } catch {
    return iso;
  }
}

/**
 * FmsAlertCenter – Glocke im Header.
 * - Polled FMS-Events alle 10s
 * - Filtert unquittierte Events mit to_fms in {0,5}
 * - Beep alle 5s solange Alarme offen (toggle via Lautsprecher-Icon)
 * - Popover-Liste mit "Quittieren" (nur EL/FA)
 * - Bei archiviertem Incident: gar nicht sichtbar
 * - Ohne aktiven Incident: gar nicht sichtbar
 */
export function FmsAlertCenter() {
  const { activeIncident } = useIncidents();
  const { role, can } = useRole();
  const incidentId = activeIncident?.id || null;
  const isArchived = activeIncident?.status === 'abgeschlossen';
  const active = Boolean(incidentId) && !isArchived;

  const [events, setEvents] = React.useState([]);
  const [open, setOpen] = React.useState(false);
  const [busyId, setBusyId] = React.useState(null);
  const [soundOn, setSoundOn] = React.useState(() => {
    if (typeof window === 'undefined') return true;
    return localStorage.getItem(SOUND_KEY) !== '0';
  });

  // Set fuer bereits "gesehene" Alert-IDs (verhindert Spam-Beep beim ersten Load).
  const seenRef = React.useRef(new Set());
  React.useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      const raw = localStorage.getItem(SEEN_KEY);
      if (raw) seenRef.current = new Set(JSON.parse(raw));
    } catch {
      /* noop */
    }
  }, []);

  const persistSeen = React.useCallback(() => {
    try {
      localStorage.setItem(
        SEEN_KEY,
        JSON.stringify(Array.from(seenRef.current).slice(-500)),
      );
    } catch {
      /* noop */
    }
  }, []);

  const fetchEvents = React.useCallback(async () => {
    if (!incidentId) return;
    try {
      const list = await listFmsEvents(incidentId, { limit: 100 });
      setEvents(list);
    } catch {
      // Silenced – polling continues
    }
  }, [incidentId]);

  // Polling
  React.useEffect(() => {
    if (!active) {
      setEvents([]);
      return undefined;
    }
    fetchEvents();
    const id = setInterval(fetchEvents, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [active, fetchEvents]);

  // Unquittierte Alerts (to_fms in {0,5})
  const unackAlerts = React.useMemo(() => {
    return events.filter((e) => {
      const to = e.to_fms;
      if (to !== 0 && to !== 5) return false;
      return !e.acknowledged_at;
    });
  }, [events]);

  // Erst-Load-Detection: alle bereits existierenden Alerts als "gesehen" markieren
  // damit beim Page-Refresh kein Beep ausgeloest wird. Nur das initiale Set.
  const firstLoadRef = React.useRef(true);
  React.useEffect(() => {
    if (!active) return;
    if (firstLoadRef.current && events.length > 0) {
      for (const e of unackAlerts) seenRef.current.add(e.id);
      persistSeen();
      firstLoadRef.current = false;
    }
  }, [active, events, unackAlerts, persistSeen]);

  // Beep beim Eintreffen eines neuen (ungesehenen) Alerts + periodisch alle 5s
  React.useEffect(() => {
    if (!active || !soundOn) return undefined;
    const newAlerts = unackAlerts.filter((e) => !seenRef.current.has(e.id));
    if (newAlerts.length > 0) {
      playBeep();
      for (const e of newAlerts) seenRef.current.add(e.id);
      persistSeen();
    }
    if (unackAlerts.length === 0) return undefined;
    // periodischer Beep alle 5s solange unquittiert
    const id = setInterval(() => {
      if (!soundOn) return;
      playBeep();
    }, BEEP_INTERVAL_MS);
    return () => clearInterval(id);
  }, [active, soundOn, unackAlerts, persistSeen]);

  const toggleSound = React.useCallback(() => {
    setSoundOn((v) => {
      const next = !v;
      try {
        localStorage.setItem(SOUND_KEY, next ? '1' : '0');
      } catch {
        /* noop */
      }
      return next;
    });
  }, []);

  const handleAck = React.useCallback(
    async (event) => {
      if (!role || !can('fms.acknowledge')) {
        toast.error('Nur EL/FA duerfen quittieren.');
        return;
      }
      setBusyId(event.id);
      try {
        const updated = await acknowledgeFmsEvent(event.id, role);
        setEvents((prev) =>
          prev.map((e) => (e.id === event.id ? { ...e, ...updated } : e)),
        );
        toast.success('FMS-Alarm quittiert');
      } catch (err) {
        const detail = err?.response?.data?.detail || err?.message || 'Quittieren fehlgeschlagen';
        toast.error(detail);
      } finally {
        setBusyId(null);
      }
    },
    [role, can],
  );

  if (!active) return null;

  const hasAlerts = unackAlerts.length > 0;
  const BellIcon = hasAlerts ? BellRing : Bell;
  const canAck = can('fms.acknowledge');

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          data-testid="fms-alert-bell"
          aria-label={
            hasAlerts
              ? `${unackAlerts.length} unquittierte FMS-Alarme`
              : 'FMS-Alarme'
          }
          className={cn(
            'relative inline-flex h-8 w-8 items-center justify-center rounded-md border border-border bg-surface-raised text-foreground transition-colors els-focus-ring',
            hasAlerts && 'border-red-500/60 text-red-500 fms-bell-pulse',
          )}
        >
          <BellIcon className="h-4 w-4" />
          {hasAlerts && (
            <span
              data-testid="fms-alert-badge"
              className="absolute -top-1 -right-1 inline-flex h-4 min-w-[16px] items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-bold leading-none text-white shadow"
            >
              {unackAlerts.length}
            </span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="end"
        className="w-[360px] p-0"
        data-testid="fms-alert-popover"
      >
        <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
          <div className="flex items-center gap-2">
            <BellIcon className={cn('h-4 w-4', hasAlerts ? 'text-red-500' : 'text-muted-foreground')} />
            <span className="text-body font-medium">FMS-Sprechwunsch</span>
            {hasAlerts && (
              <StatusBadge tone="red" variant="soft" size="sm">
                {unackAlerts.length} offen
              </StatusBadge>
            )}
          </div>
          <Button
            type="button"
            size="icon"
            variant="ghost"
            onClick={toggleSound}
            title={soundOn ? 'Ton ausschalten' : 'Ton einschalten'}
            data-testid="fms-alert-sound-toggle"
            className="h-7 w-7"
          >
            {soundOn ? (
              <Volume2 className="h-3.5 w-3.5" />
            ) : (
              <VolumeX className="h-3.5 w-3.5 text-muted-foreground" />
            )}
          </Button>
        </div>

        {unackAlerts.length === 0 ? (
          <div
            className="px-3 py-6 text-center text-caption text-muted-foreground"
            data-testid="fms-alert-empty"
          >
            <BellOff className="mx-auto mb-2 h-5 w-5 opacity-50" />
            Keine offenen Sprechwunsch-Alarme.
          </div>
        ) : (
          <ul className="max-h-[420px] divide-y divide-border overflow-y-auto" data-testid="fms-alert-list">
            {unackAlerts.map((e) => {
              const meta = fmsMeta(e.to_fms);
              return (
                <li
                  key={e.id}
                  className="px-3 py-2.5"
                  data-testid={`fms-alert-item-${e.id}`}
                >
                  <div className="flex items-start gap-2">
                    <span
                      className="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full font-mono text-xs font-bold text-white shadow fms-bell-pulse"
                      style={{ background: meta?.color || '#ef4444' }}
                      title={meta?.label || `FMS ${e.to_fms}`}
                    >
                      {e.to_fms}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm font-medium truncate">
                          {e.resource_name || '—'}
                        </span>
                        {e.source === 'divera' ? (
                          <RadioTower className="h-3 w-3 text-emerald-500" />
                        ) : (
                          <Hand className="h-3 w-3 text-muted-foreground" />
                        )}
                      </div>
                      <div className="text-caption text-muted-foreground">
                        {meta?.label || `FMS ${e.to_fms}`}
                      </div>
                      <div className="mt-0.5 flex items-center gap-1 text-[11px] text-muted-foreground font-mono">
                        <Clock3 className="h-2.5 w-2.5" />
                        {fmtFullTime(e.ts)}
                      </div>
                    </div>
                    <Button
                      type="button"
                      size="sm"
                      variant="default"
                      onClick={() => handleAck(e)}
                      disabled={!canAck || busyId === e.id}
                      data-testid={`fms-alert-ack-${e.id}`}
                      title={
                        canAck
                          ? 'Sprechwunsch quittieren'
                          : 'Nur EL/FA duerfen quittieren'
                      }
                      className="h-7"
                    >
                      <Check className="h-3 w-3" />
                      {busyId === e.id ? '…' : 'Quitt.'}
                    </Button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}

        {!canAck && hasAlerts && (
          <div className="border-t border-border bg-amber-500/10 px-3 py-1.5 text-[11px] text-amber-300">
            Nur Einsatzleiter & Fuehrungsassistenz koennen Alarme quittieren.
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
