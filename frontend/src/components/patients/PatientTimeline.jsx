import * as React from 'react';
import { cn } from '@/lib/utils';
import { formatDuration, formatDateTime } from '@/lib/time';
import { Check, Clock3 } from 'lucide-react';

const DEFAULT_EVENTS = [
  { key: 'created_at', label: 'Ankunft' },
  { key: 'sichtung_at', label: 'Sichtung' },
  { key: 'behandlung_start_at', label: 'Behandlungsstart' },
  { key: 'transport_angefordert_at', label: 'Transport angefordert' },
  { key: 'fallabschluss_at', label: 'Fallabschluss' },
];

/**
 * PatientTimeline – vertikale Ereignis-Timeline mit Dauer-Deltas.
 */
export function PatientTimeline({ patient, events = DEFAULT_EVENTS }) {
  const [now, setNow] = React.useState(() => Date.now());
  React.useEffect(() => {
    const closed =
      patient.status === 'uebergeben' || patient.status === 'entlassen';
    if (closed) return undefined;
    const id = setInterval(() => setNow(Date.now()), 30 * 1000);
    return () => clearInterval(id);
  }, [patient.status]);

  const milestoneItems = events.map((ev, idx) => ({
    ...ev,
    order: idx,
    ts: patient[ev.key] ? new Date(patient[ev.key]).getTime() : null,
  }));

  const pendingMilestones = milestoneItems.filter((it) => it.ts === null);
  const firstPendingOrder = pendingMilestones.length
    ? pendingMilestones[0].order
    : null;

  const resourceEvents = (patient.behandlung_ressource_events || [])
    .filter((e) => e?.ts)
    .slice()
    .sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());

  const sichtungEvents = (patient.sichtung_events || [])
    .filter((e) => e?.ts)
    .slice()
    .sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());

  const SICHTUNG_LABEL = {
    S1: 'S1 (Rot)',
    S2: 'S2 (Gelb)',
    S3: 'S3 (Grün)',
    S0: 'S0 (Weiß)',
  };

  const formatResourceLabel = (entry) => {
    if (entry.action === 'assigned') {
      return `Ressource zugewiesen: ${entry.to_name || 'unbekannt'}`;
    }
    if (entry.action === 'cleared') {
      return `Ressource entfernt: ${entry.from_name || 'unbekannt'}`;
    }
    if (entry.action === 'changed') {
      return `Ressource gewechselt: ${entry.from_name || 'unbekannt'} -> ${entry.to_name || 'unbekannt'}`;
    }
    if (!entry.from_name && entry.to_name) {
      return `Ressource zugewiesen: ${entry.to_name}`;
    }
    if (entry.from_name && !entry.to_name) {
      return `Ressource entfernt: ${entry.from_name}`;
    }
    return `Ressource aktualisiert: ${entry.from_name || 'unbekannt'} -> ${entry.to_name || 'unbekannt'}`;
  };

  const timelineEntries = [];
  let seq = 0;

  for (const it of milestoneItems) {
    if (it.ts === null) continue;
    timelineEntries.push({
      kind: 'milestone',
      key: it.key,
      label: it.label,
      ts: it.ts,
      seq: seq++,
    });
  }

  for (let idx = 0; idx < (patient.wiedereroeffnet_at || []).length; idx += 1) {
    const tsRaw = patient.wiedereroeffnet_at[idx];
    const ts = tsRaw ? new Date(tsRaw).getTime() : null;
    if (!ts) continue;
    timelineEntries.push({
      kind: 'reopen',
      key: `reopen-${idx}`,
      label: `Wiedereroeffnet #${idx + 1}`,
      ts,
      seq: seq++,
    });
  }

  for (let idx = 0; idx < resourceEvents.length; idx += 1) {
    const entry = resourceEvents[idx];
    const ts = entry?.ts ? new Date(entry.ts).getTime() : null;
    if (!ts) continue;
    timelineEntries.push({
      kind: 'resource',
      key: `resource-event-${idx}-${entry.ts}`,
      label: formatResourceLabel(entry),
      resourceIndex: idx,
      ts,
      seq: seq++,
    });
  }

  for (let idx = 0; idx < sichtungEvents.length; idx += 1) {
    const entry = sichtungEvents[idx];
    const ts = entry?.ts ? new Date(entry.ts).getTime() : null;
    if (!ts) continue;
    const fromLabel =
      SICHTUNG_LABEL[entry.from_sichtung] || entry.from_sichtung || '–';
    const toLabel =
      SICHTUNG_LABEL[entry.to_sichtung] || entry.to_sichtung || '–';
    timelineEntries.push({
      kind: 'sichtung',
      key: `sichtung-event-${idx}-${entry.ts}`,
      label: `Sichtung geändert: ${fromLabel} → ${toLabel}`,
      sichtungIndex: idx,
      ts,
      seq: seq++,
    });
  }

  timelineEntries.sort((a, b) => a.ts - b.ts || a.seq - b.seq);

  const entriesWithDelta = timelineEntries.map((entry, idx) => ({
    ...entry,
    delta: idx > 0 ? entry.ts - timelineEntries[idx - 1].ts : null,
  }));

  const lastTimestamp = entriesWithDelta.length
    ? entriesWithDelta[entriesWithDelta.length - 1].ts
    : null;

  return (
    <ol className="relative space-y-3" data-testid="patient-timeline">
      {entriesWithDelta.map((it, i) => {
        const toneDot =
          it.kind === 'reopen'
            ? 'bg-status-yellow'
            : it.kind === 'resource'
              ? 'bg-primary/70'
              : it.kind === 'sichtung'
                ? 'bg-orange-400'
                : 'bg-primary';
        const toneText =
          it.kind === 'reopen'
            ? 'text-status-yellow'
            : it.kind === 'sichtung'
              ? 'text-orange-400'
              : 'text-foreground';
        return (
          <li
            key={it.key}
            data-testid={
              it.kind === 'resource'
                ? `timeline-resource-${it.resourceIndex}`
                : it.kind === 'sichtung'
                  ? `timeline-sichtung-${it.sichtungIndex}`
                  : `timeline-${it.key}`
            }
            className="flex items-start gap-3"
          >
            <div className="relative flex h-5 w-5 shrink-0 items-center justify-center">
              <span className={cn('block h-2.5 w-2.5 rounded-full', toneDot)} />
              {i < entriesWithDelta.length - 1 && (
                <span
                  aria-hidden
                  className={cn(
                    'absolute left-1/2 top-5 h-[calc(100%+0.5rem)] w-px -translate-x-1/2',
                    'bg-primary/40',
                  )}
                />
              )}
            </div>
            <div className="flex-1 pb-1 text-body">
              <div className="flex items-center justify-between gap-2">
                <span className={cn('font-medium', toneText)}>{it.label}</span>
                <Check className="h-3.5 w-3.5 text-primary" />
              </div>
              <div className="flex items-center gap-2 text-caption text-muted-foreground">
                <span className="font-mono">{formatDateTime(it.ts)}</span>
                {it.delta != null && (
                  <span className="rounded bg-surface-raised px-1.5 py-0.5 font-mono tabular-nums">
                    +{formatDuration(it.delta)}
                  </span>
                )}
              </div>
            </div>
          </li>
        );
      })}

      {pendingMilestones.map((it) => {
        const isNext = firstPendingOrder === it.order;
        return (
          <li
            key={it.key}
            data-testid={`timeline-${it.key}`}
            className="flex items-start gap-3"
          >
            <div className="relative flex h-5 w-5 shrink-0 items-center justify-center">
              <span
                className={cn(
                  'block h-2.5 w-2.5 rounded-full',
                  isNext ? 'bg-status-yellow animate-pulse-ring' : 'bg-muted',
                )}
              />
            </div>
            <div className="flex-1 pb-1 text-body">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-muted-foreground">
                  {it.label}
                </span>
                {isNext ? (
                  <Clock3 className="h-3.5 w-3.5 text-status-yellow" />
                ) : null}
              </div>
              <div className="flex items-center gap-2 text-caption text-muted-foreground">
                <span>offen</span>
              </div>
            </div>
          </li>
        );
      })}

      {/* Live-Dauer seit letztem Event (wenn nicht abgeschlossen) */}
      {patient.status !== 'uebergeben' &&
        patient.status !== 'entlassen' &&
        lastTimestamp && (
          <li className="flex items-start gap-3" data-testid="timeline-live">
            <div className="flex h-5 w-5 shrink-0 items-center justify-center">
              <span className="block h-1.5 w-1.5 rounded-full bg-muted" />
            </div>
            <div className="text-caption text-muted-foreground">
              seit letztem Ereignis ·
              <span className="ml-1 font-mono tabular-nums">
                {formatDuration(now - lastTimestamp)}
              </span>
            </div>
          </li>
        )}
    </ol>
  );
}
