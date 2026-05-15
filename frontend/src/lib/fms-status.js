/**
 * BOS-Funkmeldesystem (FMS) Status-Mapping.
 * Quelle: BOS-Standardbedeutungen, an Divera-Integration angepasst.
 */
export const FMS_STATUS = {
  0: {
    label: 'Priorisierter Sprechwunsch',
    short: '0',
    tone: 'red',
    color: '#ef4444',
    group: 'sprechwunsch',
    available: false,
  },
  1: {
    label: 'Einsatzbereit über Funk',
    short: '1',
    tone: 'green',
    color: '#22c55e',
    group: 'verfuegbar',
    available: true,
  },
  2: {
    label: 'Einsatzbereit auf Wache',
    short: '2',
    tone: 'green',
    color: '#16a34a',
    group: 'verfuegbar',
    available: true,
  },
  3: {
    label: 'Einsatzauftrag übernommen',
    short: '3',
    tone: 'yellow',
    color: '#eab308',
    group: 'einsatz',
    available: false,
  },
  4: {
    label: 'Ankunft Einsatzort',
    short: '4',
    tone: 'yellow',
    color: '#f59e0b',
    group: 'einsatz',
    available: false,
  },
  5: {
    label: 'Sprechwunsch',
    short: '5',
    tone: 'blue',
    color: '#3b82f6',
    group: 'sprechwunsch',
    available: false,
  },
  6: {
    label: 'Nicht einsatzbereit',
    short: '6',
    tone: 'gray',
    color: '#6b7280',
    group: 'offline',
    available: false,
  },
  7: {
    label: 'Patient aufgenommen',
    short: '7',
    tone: 'yellow',
    color: '#d97706',
    group: 'einsatz',
    available: false,
  },
  8: {
    label: 'Am Transportziel',
    short: '8',
    tone: 'yellow',
    color: '#b45309',
    group: 'einsatz',
    available: false,
  },
  9: {
    label: 'Wartung / nicht verfügbar',
    short: '9',
    tone: 'gray',
    color: '#475569',
    group: 'wartung',
    available: false,
  },
};

export function fmsMeta(status) {
  if (status === null || status === undefined) return null;
  return FMS_STATUS[Number(status)] || null;
}

/** Map FMS status to ELS internal resource status. */
export function fmsToResourceStatus(fms) {
  const meta = fmsMeta(fms);
  if (!meta) return null;
  if (meta.group === 'verfuegbar') return 'verfuegbar';
  if (meta.group === 'einsatz') return 'im_einsatz';
  if (meta.group === 'offline' || meta.group === 'wartung') return 'offline';
  return null; // sprechwunsch keeps existing status
}
