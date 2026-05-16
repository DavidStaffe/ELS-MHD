import * as React from 'react';
import { listFmsEvents } from '@/lib/api';
import { fmsMeta } from '@/lib/fms-status';
import { StatusBadge } from '@/components/primitives';
import { Button } from '@/components/ui/button';
import { History, RefreshCw, RadioTower, Hand, ArrowRight, Clock3, Check } from 'lucide-react';

const ROLE_KURZ = {
  einsatzleiter: 'EL',
  fuehrungsassistenz: 'FA',
  abschnittleitung: 'AL',
  helfer: 'Helfer',
  dokumentar: 'DOK',
};

function fmtDuration(ms) {
  if (ms == null || ms < 0) return '–';
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  const rest = m % 60;
  return rest ? `${h}h ${rest}m` : `${h}h`;
}

function fmtTime(iso) {
  if (!iso) return '–';
  try {
    return new Date(iso).toLocaleString('de-DE', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      day: '2-digit',
      month: '2-digit',
    });
  } catch {
    return iso;
  }
}

/**
 * FmsHistory – chronologische Liste der FMS-Aenderungen.
 * Props:
 *   incidentId
 *   resourceId  (optional) – filtert auf einzelne Ressource
 *   limit (default 50)
 *   showResourceName (default true) – Spalte mit Resource-Name
 *   compact (default false)
 */
export function FmsHistory({
  incidentId,
  resourceId = null,
  limit = 50,
  showResourceName = true,
  compact = false,
}) {
  const [events, setEvents] = React.useState([]);
  const [loading, setLoading] = React.useState(false);

  const load = React.useCallback(async () => {
    if (!incidentId) return;
    setLoading(true);
    try {
      const list = await listFmsEvents(incidentId, { resourceId, limit });
      setEvents(list);
    } catch (e) {
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }, [incidentId, resourceId, limit]);

  React.useEffect(() => {
    load();
  }, [load]);

  // Berechne Dauer im vorherigen Status pro Resource
  // events kommen 'neueste zuerst', wir kehren um fuer chronologische Verarbeitung
  const enriched = React.useMemo(() => {
    // group by resource_id, sort asc within
    const byRes = new Map();
    for (const e of events) {
      const arr = byRes.get(e.resource_id) || [];
      arr.push(e);
      byRes.set(e.resource_id, arr);
    }
    for (const arr of byRes.values()) {
      arr.sort((a, b) => new Date(a.ts) - new Date(b.ts));
      for (let i = 0; i < arr.length; i++) {
        const cur = arr[i];
        const next = arr[i + 1];
        cur.duration_ms = next ? new Date(next.ts) - new Date(cur.ts) : null;
      }
    }
    // Re-sort all events desc (neueste zuerst)
    return [...events].sort((a, b) => new Date(b.ts) - new Date(a.ts));
  }, [events]);

  return (
    <div className="space-y-2" data-testid="fms-history">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-caption text-muted-foreground">
          <History className="h-3.5 w-3.5" />
          <span className="uppercase tracking-wider">
            FMS-Verlauf {events.length > 0 && `(${events.length})`}
          </span>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-6 w-6 p-0"
          onClick={load}
          disabled={loading}
          title="Neu laden"
          data-testid="fms-history-reload"
        >
          <RefreshCw className={'h-3 w-3 ' + (loading ? 'animate-spin' : '')} />
        </Button>
      </div>

      {enriched.length === 0 ? (
        <div className="text-caption text-muted-foreground italic" data-testid="fms-history-empty">
          {loading ? 'Lade…' : 'Noch keine FMS-Aenderungen aufgezeichnet.'}
        </div>
      ) : (
        <ol className="space-y-1" data-testid="fms-history-list">
          {enriched.map((e) => {
            const fromMeta = fmsMeta(e.from_fms);
            const toMeta = fmsMeta(e.to_fms);
            const isAlert = e.to_fms === 0 || e.to_fms === 5;
            const ackRole = e.acknowledged_by_role;
            const ackAt = e.acknowledged_at;
            return (
              <li
                key={e.id}
                className={
                  'rounded-md bg-surface-raised px-2 py-1 ' +
                  (compact ? 'text-[11px]' : 'text-caption')
                }
                data-testid={`fms-event-${e.id}`}
              >
                <div className="flex items-center gap-2">
                  {e.source === 'divera' ? (
                    <RadioTower
                      className="h-3 w-3 shrink-0 text-emerald-500"
                      title="Divera-Sync"
                    />
                  ) : (
                    <Hand
                      className="h-3 w-3 shrink-0 text-muted-foreground"
                      title="Manuell"
                    />
                  )}

                  {showResourceName && (
                    <span
                      className="font-medium truncate min-w-0 max-w-[100px]"
                      title={e.resource_name || ''}
                    >
                      {e.resource_name || '—'}
                    </span>
                  )}

                  <span className="flex items-center gap-1 shrink-0">
                    <span
                      className="font-mono font-semibold tabular-nums"
                      style={{ color: fromMeta?.color || '#94a3b8' }}
                      title={fromMeta?.label || 'kein FMS'}
                    >
                      {e.from_fms ?? '–'}
                    </span>
                    <ArrowRight className="h-2.5 w-2.5 text-muted-foreground" />
                    <span
                      className="font-mono font-semibold tabular-nums"
                      style={{ color: toMeta?.color || '#94a3b8' }}
                      title={toMeta?.label || 'kein FMS'}
                    >
                      {e.to_fms ?? '–'}
                    </span>
                  </span>

                  {isAlert && !ackAt && (
                    <StatusBadge tone="red" variant="soft" size="sm">
                      Sprechwunsch
                    </StatusBadge>
                  )}

                  {e.duration_ms != null && (
                    <span className="inline-flex items-center gap-1 text-muted-foreground tabular-nums">
                      <Clock3 className="h-2.5 w-2.5" />
                      {fmtDuration(e.duration_ms)}
                    </span>
                  )}

                  <span className="ml-auto font-mono text-muted-foreground tabular-nums whitespace-nowrap">
                    {fmtTime(e.ts)}
                  </span>
                </div>
                {isAlert && ackAt && (
                  <div
                    className="mt-0.5 ml-5 flex items-center gap-1 text-[10px] text-emerald-400"
                    data-testid={`fms-event-ack-${e.id}`}
                  >
                    <Check className="h-2.5 w-2.5" />
                    quittiert von {ROLE_KURZ[ackRole] || ackRole || '—'} um{' '}
                    <span className="font-mono">{fmtTime(ackAt)}</span>
                  </div>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
