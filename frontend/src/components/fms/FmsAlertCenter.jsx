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
import { fmsMeta } from '@/lib/fms-status';
import { useFmsAlerts } from '@/components/fms/useFmsAlerts';
import { toast } from 'sonner';

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
 * Konsumiert useFmsAlerts (Polling+SSE+Beep zentral).
 * Bei archiviertem/keinem Incident: gar nicht sichtbar.
 */
export function FmsAlertCenter() {
  const [open, setOpen] = React.useState(false);
  const {
    active,
    unackAlerts,
    busyId,
    soundOn,
    toggleSound,
    acknowledge,
    canAcknowledge,
  } = useFmsAlerts();

  const handleAck = React.useCallback(async (event) => {
    const res = await acknowledge(event);
    if (res.ok) toast.success('FMS-Alarm quittiert');
    else if (res.error === 'permission') toast.error('Nur EL/FA duerfen quittieren.');
    else toast.error(res.error);
  }, [acknowledge]);

  if (!active) return null;

  const hasAlerts = unackAlerts.length > 0;
  const BellIcon = hasAlerts ? BellRing : Bell;

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
                      disabled={!canAcknowledge || busyId === e.id}
                      data-testid={`fms-alert-ack-${e.id}`}
                      title={
                        canAcknowledge
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

        {!canAcknowledge && hasAlerts && (
          <div className="border-t border-border bg-amber-500/10 px-3 py-1.5 text-[11px] text-amber-300">
            Nur Einsatzleiter & Fuehrungsassistenz koennen Alarme quittieren.
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
