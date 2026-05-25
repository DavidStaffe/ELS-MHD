import * as React from 'react';
import { AlertOctagon, Check, Clock3, RadioTower, Hand, Volume2, VolumeX } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { fmsMeta } from '@/lib/fms-status';
import { useFmsAlerts } from '@/components/fms/useFmsAlerts';
import { toast } from 'sonner';

function fmtFullTime(iso) {
  if (!iso) return '–';
  try {
    return new Date(iso).toLocaleString('de-DE', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return iso;
  }
}

/**
 * FmsAlertSidebarPanel – grosses prominentes Alarm-Panel.
 * Wird sichtbar SOBALD ein unquittierter FMS-5/0-Alarm vorliegt.
 * - Roter pulsierender Kasten oben in der Sidebar (Karte).
 * - Listet alle offenen Sprechwuensche mit Fahrzeug + FMS + Zeit.
 * - Quittieren-Button pro Eintrag (nur EL/FA aktiv).
 * Im Gegensatz zur Glocke (Popover, klein) ist dies eine PERMANENTE Anzeige.
 */
export function FmsAlertSidebarPanel() {
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

  if (!active || unackAlerts.length === 0) return null;

  return (
    <section
      data-testid="fms-alert-sidebar-panel"
      className="relative overflow-hidden rounded-lg border-2 border-red-500/70 bg-red-950/40 shadow-[0_0_0_4px_rgba(239,68,68,0.15)]"
    >
      {/* Pulse overlay */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-0 fms-bell-pulse"
        style={{ borderRadius: 'inherit' }}
      />
      <header className="relative flex items-center justify-between gap-2 border-b border-red-500/30 bg-red-600/30 px-3 py-2">
        <div className="flex items-center gap-2">
          <AlertOctagon className="h-5 w-5 text-red-300 animate-pulse" />
          <div className="leading-tight">
            <div className="text-sm font-bold uppercase tracking-wider text-red-100">
              Sprechwunsch
            </div>
            <div className="text-[11px] text-red-200/80">
              {unackAlerts.length} offen
              {!canAcknowledge && ' · Quittierung nur durch EL/FA'}
            </div>
          </div>
        </div>
        <Button
          type="button"
          size="icon"
          variant="ghost"
          onClick={toggleSound}
          title={soundOn ? 'Ton ausschalten' : 'Ton einschalten'}
          data-testid="fms-alert-sidebar-sound"
          className="h-7 w-7 text-red-100 hover:bg-red-500/30 hover:text-white"
        >
          {soundOn ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
        </Button>
      </header>

      <ul
        className="relative max-h-[280px] divide-y divide-red-500/20 overflow-y-auto"
        data-testid="fms-alert-sidebar-list"
      >
        {unackAlerts.map((e) => {
          const meta = fmsMeta(e.to_fms);
          return (
            <li
              key={e.id}
              className="flex items-center gap-2.5 bg-red-950/30 px-3 py-2"
              data-testid={`fms-alert-sidebar-item-${e.id}`}
            >
              <span
                className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full font-mono text-base font-bold text-white shadow-lg fms-bell-pulse"
                style={{ background: meta?.color || '#ef4444' }}
                title={meta?.label || `FMS ${e.to_fms}`}
              >
                {e.to_fms}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <span
                    className="truncate text-sm font-semibold text-red-50"
                    title={e.resource_name || ''}
                  >
                    {e.resource_name || '—'}
                  </span>
                  {e.source === 'divera' ? (
                    <RadioTower className="h-3 w-3 shrink-0 text-emerald-300" />
                  ) : (
                    <Hand className="h-3 w-3 shrink-0 text-red-200/70" />
                  )}
                </div>
                <div className="flex items-center gap-1 text-[11px] text-red-200/70">
                  <Clock3 className="h-2.5 w-2.5" />
                  <span className="font-mono tabular-nums">{fmtFullTime(e.ts)}</span>
                  <span className="ml-1 truncate italic">
                    {meta?.label || `FMS ${e.to_fms}`}
                  </span>
                </div>
              </div>
              <Button
                type="button"
                size="sm"
                onClick={() => handleAck(e)}
                disabled={!canAcknowledge || busyId === e.id}
                data-testid={`fms-alert-sidebar-ack-${e.id}`}
                title={
                  canAcknowledge
                    ? 'Sprechwunsch quittieren'
                    : 'Nur EL/FA duerfen quittieren'
                }
                className="h-8 bg-red-600 px-3 text-white hover:bg-red-500 disabled:bg-red-900 disabled:text-red-300/50"
              >
                <Check className="h-3.5 w-3.5" />
                {busyId === e.id ? '…' : 'Quittieren'}
              </Button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
