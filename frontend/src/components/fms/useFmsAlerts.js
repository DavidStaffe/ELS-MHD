import * as React from 'react';
import { API_BASE, listFmsEvents, acknowledgeFmsEvent } from '@/lib/api';
import { useIncidents } from '@/context/IncidentContext';
import { useRole } from '@/context/RoleContext';

const POLL_INTERVAL_MS = 10000;
const BEEP_INTERVAL_MS = 5000;
const SOUND_KEY = 'els-fms-alert-sound';
const SEEN_KEY = 'els-fms-alert-seen';

/**
 * Web-Audio 2-Ton-Beep — keine Asset-Datei noetig.
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
    setTimeout(() => ctx.close().catch(() => {}), 600);
  } catch {
    /* noop */
  }
}

/**
 * Zentraler Hook fuer FMS-Sprechwunsch-Alarme.
 * - Polled alle 10s als Fallback.
 * - SSE-Listener auf /incidents/stream fuer Echtzeit-Push bei FMS-Aenderungen.
 * - Beep bei neuen Alerts + alle 5s solange offen (Toggle persistiert localStorage).
 * - Quittierung via acknowledgeFmsEvent + sofortiges lokales Update.
 * - Bei archiviertem/keinem Incident: leere Listen + keine Aktivitaet.
 */
export function useFmsAlerts() {
  const { activeIncident } = useIncidents();
  const { role, userName, can } = useRole();
  const incidentId = activeIncident?.id || null;
  const isArchived = activeIncident?.status === 'abgeschlossen';
  const active = Boolean(incidentId) && !isArchived;

  const [events, setEvents] = React.useState([]);
  const [busyId, setBusyId] = React.useState(null);
  const [soundOn, setSoundOn] = React.useState(() => {
    if (typeof window === 'undefined') return true;
    return localStorage.getItem(SOUND_KEY) !== '0';
  });

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
      /* silent */
    }
  }, [incidentId]);

  // Initial + Polling alle 10s
  React.useEffect(() => {
    if (!active) {
      setEvents([]);
      return undefined;
    }
    fetchEvents();
    const id = setInterval(fetchEvents, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [active, fetchEvents]);

  // SSE: sofortiger Push bei neuen FMS-Events + Quittierungen
  React.useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    if (!active) return undefined;

    let disposed = false;
    let es = null;
    let reconnectTimer = null;
    let refreshTimer = null;

    const scheduleRefresh = () => {
      if (refreshTimer) window.clearTimeout(refreshTimer);
      refreshTimer = window.setTimeout(() => {
        fetchEvents();
      }, 150);
    };

    const connect = () => {
      if (disposed) return;
      try {
        es = new EventSource(`${API_BASE}/incidents/stream`);
      } catch {
        reconnectTimer = window.setTimeout(connect, 2000);
        return;
      }
      es.addEventListener('incident', (e) => {
        try {
          const data = JSON.parse(e.data || '{}');
          if (data?.incident_id && data.incident_id !== incidentId) return;
          if (
            data?.kind === 'fms_event' ||
            data?.type === 'fms_event_acknowledged'
          ) {
            scheduleRefresh();
          }
        } catch {
          /* noop */
        }
      });
      es.onerror = () => {
        try { es?.close(); } catch { /* noop */ }
        es = null;
        if (!disposed) reconnectTimer = window.setTimeout(connect, 2000);
      };
    };

    connect();
    return () => {
      disposed = true;
      if (refreshTimer) window.clearTimeout(refreshTimer);
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      try { es?.close(); } catch { /* noop */ }
    };
  }, [active, incidentId, fetchEvents]);

  // Unquittierte Alerts (to_fms in {0,5})
  const unackAlerts = React.useMemo(() => {
    return events.filter((e) => {
      const to = e.to_fms;
      if (to !== 0 && to !== 5) return false;
      return !e.acknowledged_at;
    });
  }, [events]);

  // Beim ersten Laden: bereits existierende Alerts als gesehen markieren
  // damit kein Beep-Spam bei Page-Refresh entsteht.
  const firstLoadRef = React.useRef(true);
  React.useEffect(() => {
    if (!active) return;
    if (firstLoadRef.current && events.length > 0) {
      for (const e of unackAlerts) seenRef.current.add(e.id);
      persistSeen();
      firstLoadRef.current = false;
    }
  }, [active, events, unackAlerts, persistSeen]);

  // Beep bei neuen Alerts + alle 5s solange unquittiert
  React.useEffect(() => {
    if (!active || !soundOn) return undefined;
    const newAlerts = unackAlerts.filter((e) => !seenRef.current.has(e.id));
    if (newAlerts.length > 0) {
      playBeep();
      for (const e of newAlerts) seenRef.current.add(e.id);
      persistSeen();
    }
    if (unackAlerts.length === 0) return undefined;
    const id = setInterval(() => {
      if (!soundOn) return;
      playBeep();
    }, BEEP_INTERVAL_MS);
    return () => clearInterval(id);
  }, [active, soundOn, unackAlerts, persistSeen]);

  const toggleSound = React.useCallback(() => {
    setSoundOn((v) => {
      const next = !v;
      try { localStorage.setItem(SOUND_KEY, next ? '1' : '0'); } catch { /* noop */ }
      return next;
    });
  }, []);

  const acknowledge = React.useCallback(async (event) => {
    if (!role || !can('fms.acknowledge')) return { ok: false, error: 'permission' };
    setBusyId(event.id);
    try {
      const updated = await acknowledgeFmsEvent(event.id, role, userName);
      setEvents((prev) =>
        prev.map((e) => (e.id === event.id ? { ...e, ...updated } : e)),
      );
      return { ok: true };
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || 'Quittieren fehlgeschlagen';
      return { ok: false, error: detail };
    } finally {
      setBusyId(null);
    }
  }, [role, userName, can]);

  return {
    active,
    incidentId,
    role,
    canAcknowledge: Boolean(role) && can('fms.acknowledge'),
    events,
    unackAlerts,
    busyId,
    soundOn,
    toggleSound,
    acknowledge,
    refresh: fetchEvents,
  };
}
