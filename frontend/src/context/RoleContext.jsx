import * as React from "react";
import { api } from '@/lib/api';
import { IdentityGate } from '@/components/shell/IdentityGate';

/**
 * Rollen & Rechte-Definition.
 * Abgeleitet aus Handlungsablauf + Gesamtspezifikation:
 *   - einsatzleiter: Vollzugriff, Freigabe Abschlussbericht
 *   - helfer: Patientenerfassung, Zeitstempel, Transportanforderung, Konfliktmeldung
 *   - dokumentar: Nachbearbeitung, Berichtsvorschau, PDF-Export
 */
export const ROLES = {
    einsatzleiter: {
        key: "einsatzleiter",
        label: "Einsatzleiter",
        kurz: "EL",
        tone: "info",
        beschreibung: "Vollzugriff auf alle Module. Freigabe des Abschlussberichts."
    },
    fuehrungsassistenz: {
        key: "fuehrungsassistenz",
        label: "Fuehrungsassistenz Funk/Doku",
        kurz: "FA",
        tone: "blue",
        beschreibung: "Volle Schreib- und Dokumentationsrechte im Funktagebuch."
    },
    abschnittleitung: {
        key: "abschnittleitung",
        label: "Abschnittleitung",
        kurz: "AL",
        tone: "purple",
        beschreibung: "Abschnittsbezogene Meldungen erfassen und rueckmelden (UHS/BHP etc.)."
    },
    helfer: {
        key: "helfer",
        label: "Sanitaeter / Helfer",
        kurz: "HELFER",
        tone: "green",
        beschreibung: "Patientenerfassung, Sichtung, Transportanforderung, Meldungen."
    },
    dokumentar: {
        key: "dokumentar",
        label: "Dokumentar",
        kurz: "DOK",
        tone: "yellow",
        beschreibung: "Nachbearbeitung, Berichtsvorschau und PDF-Export."
    }
};

export const ROLE_KEYS = Object.keys(ROLES);

/**
 * Permission-Matrix.
 * "can(action)" liefert true/false abhaengig von der aktiven Rolle.
 */
const PERMS = {
    // Incidents
    "incident.create": ["einsatzleiter"],
    "incident.update": ["einsatzleiter", "fuehrungsassistenz"],
    "incident.delete": ["einsatzleiter"],
    "incident.close": ["einsatzleiter"],
    "incident.demo_start": ["einsatzleiter", "fuehrungsassistenz", "abschnittleitung", "helfer", "dokumentar"],

    // Patienten
    "patient.create": ["einsatzleiter", "helfer"],
    "patient.update": ["einsatzleiter", "helfer"],
    "patient.delete": ["einsatzleiter"],
    "patient.progress": ["einsatzleiter", "helfer"],
    "patient.reopen": ["einsatzleiter", "helfer"],

    // Transport
    "transport.create": ["einsatzleiter"],
    "transport.assign": ["einsatzleiter", "helfer"],
    "transport.status": ["einsatzleiter", "helfer"],
    "transport.delete": ["einsatzleiter"],

    // Ressourcen
    "resource.view": ["einsatzleiter", "fuehrungsassistenz", "abschnittleitung", "helfer", "dokumentar"],
    "resource.update": ["einsatzleiter", "helfer"],
    "resource.create": ["einsatzleiter"],
    "resource.delete": ["einsatzleiter"],

    // Kommunikation / Funktagebuch
    "message.view": ["einsatzleiter", "fuehrungsassistenz", "abschnittleitung", "helfer", "dokumentar"],
    "message.create": ["einsatzleiter", "fuehrungsassistenz", "abschnittleitung", "helfer"],
    "message.update": ["einsatzleiter", "fuehrungsassistenz"],
    "message.ack": ["einsatzleiter", "fuehrungsassistenz", "helfer"],
    "message.confirm": ["einsatzleiter"],
    "message.finalize": ["einsatzleiter", "fuehrungsassistenz"],
    "message.delete": ["einsatzleiter", "fuehrungsassistenz"],

    // Konflikte
    "konflikt.resolve": ["einsatzleiter", "helfer"],

    // FMS-Sprechwunsch-Alarm-Quittierung (Sidebar/Header-Glocke)
    "fms.acknowledge": ["einsatzleiter", "fuehrungsassistenz"],

    // Abschluss
    "abschluss.view": ["einsatzleiter", "dokumentar"],
    "abschluss.freigabe": ["einsatzleiter"],
    "abschluss.export_pdf": ["einsatzleiter", "dokumentar"],
    "abschluss.edit_meta": ["einsatzleiter", "dokumentar"],
    "abschluss.version_create": ["einsatzleiter"],

    // Schritt 10: Einsatzabschnitte
    "abschnitt.view": ["einsatzleiter", "helfer", "dokumentar"],
    "abschnitt.create": ["einsatzleiter"],
    "abschnitt.update": ["einsatzleiter"],
    "abschnitt.delete": ["einsatzleiter"],
    "abschnitt.assign_resource": ["einsatzleiter", "helfer"],

    // Schritt 11: Behandlungsbetten
    "bett.view": ["einsatzleiter", "helfer", "dokumentar"],
    "bett.create": ["einsatzleiter"],
    "bett.update": ["einsatzleiter", "helfer"],
    "bett.delete": ["einsatzleiter"],
    "bett.assign_patient": ["einsatzleiter", "helfer"],
    "bett.release": ["einsatzleiter", "helfer"]
};

export function canRole(role, action) {
    if (!Object.hasOwn(PERMS, action) || !role || action.includes('delete') || action === 'incident.demo_start') return false;
    if (role === 'einsatzleiter') return true;
    if (role === 'fuehrungsassistenz') return !['incident.close','abschluss.freigabe','abschluss.version_create'].includes(action);
    if (role === 'abschnittleitung') return ['resource.view','resource.update','message.view','message.create','message.update','patient.create','patient.update','patient.progress','patient.reopen','transport.create','transport.assign','transport.status','abschnitt.view','abschnitt.update','bett.view','bett.update','bett.assign_patient','bett.release'].includes(action);
    if (role === 'dokumentar') return ['resource.view','message.view','message.create','message.update','abschnitt.view'].includes(action);
    return ['resource.view','patient.update'].includes(action);
}

const RoleContext = React.createContext(null);
const ROLE_MAP = { EL: 'einsatzleiter', FueAss: 'fuehrungsassistenz', AL: 'abschnittleitung', Dokumentar: 'dokumentar', Helfer: 'helfer' };
const GLOBAL_ACTIONS = { 'incident.create': 'incidents.create', 'users.manage': 'users.manage', 'settings.manage': 'settings.manage' };

export function useRole() {
    const ctx = React.useContext(RoleContext);
    if (!ctx) throw new Error('useRole muss innerhalb des RoleProvider genutzt werden');
    return ctx;
}

export function RoleProvider({ children }) {
    const [session, setSession] = React.useState(null);
    const [loading, setLoading] = React.useState(true);
    const [pickerOpen, setPickerOpen] = React.useState(false);
    const [activeId, setActiveId] = React.useState(() => localStorage.getItem('els-active-incident'));
    const lastActivity = React.useRef(Date.now());
    const reported = React.useRef(0);
    const sessionEpoch = React.useRef(0);
    const userId = session?.user?.id;
    const locked = session?.locked;
    const mustChange = session?.user?.must_change_password;
    const refresh = React.useCallback(async () => {
        const epoch = sessionEpoch.current;
        try {
            const { data } = await api.get('/auth/me');
            if (epoch !== sessionEpoch.current) return null;
            api.defaults.headers.common['X-CSRF-Token'] = data.csrf;
            if (sessionStorage.getItem('els-workstation-locked') && !data.locked) {
                await api.post('/auth/lock');
                data.locked = true;
            }
            setSession(data);
            return data;
        } catch { if (epoch === sessionEpoch.current) setSession(null); }
        finally { setLoading(false); }
    }, []);
    const logout = React.useCallback(async () => {
        sessionEpoch.current += 1;
        setSession(s => s ? { ...s, locked: true } : s);
        try {
            await api.post('/auth/logout');
            setSession(null); setPickerOpen(false);
            sessionStorage.removeItem('els-workstation-locked');
            delete api.defaults.headers.common['X-CSRF-Token'];
            localStorage.removeItem('els-active-incident');
            window.history.replaceState(null, '', '/');
        } catch { sessionStorage.setItem('els-workstation-locked', '1'); setSession(s => s ? { ...s, locked: true, notice: 'Abmeldung wurde vom Server nicht bestätigt. Verbindung prüfen und erneut abmelden.' } : s); }
    }, []);
    const lock = React.useCallback(async () => {
        sessionEpoch.current += 1;
        sessionStorage.setItem('els-workstation-locked', '1');
        setSession(s => s ? { ...s, locked: true } : s);
        setPickerOpen(false);
        try { await api.post('/auth/lock'); } catch { /* The UI stays locked on errors. */ }
    }, []);
    React.useEffect(() => {
        localStorage.removeItem('els-role'); localStorage.removeItem('els-user-name');
        refresh();
        const id = api.interceptors.response.use(r => r, error => {
            if (error?.response?.status === 423) { sessionEpoch.current += 1; setSession(s => s ? { csrf: s.csrf, locked: true } : s); }
            if (error?.response?.status === 401 && !error.config?.url?.startsWith('/auth/')) setSession(null);
            return Promise.reject(error);
        });
        return () => api.interceptors.response.eject(id);
    }, [refresh]);
    React.useEffect(() => {
        const changed = () => { setActiveId(localStorage.getItem('els-active-incident')); refresh(); };
        window.addEventListener('els-incident-changed', changed);
        return () => window.removeEventListener('els-incident-changed', changed);
    }, [refresh]);
    React.useEffect(() => {
        if (!userId || locked || mustChange) return undefined;
        lastActivity.current = Date.now();
        const activity = (event) => {
            if (!event.isTrusted) return;
            lastActivity.current = Date.now();
            if (Date.now() - reported.current > 15000) {
                reported.current = Date.now();
                api.post('/auth/activity').catch(() => {});
            }
        };
        const events = ['pointerdown', 'pointermove', 'keydown', 'touchstart', 'wheel'];
        events.forEach(e => window.addEventListener(e, activity, { passive: true }));
        const timer = window.setInterval(() => {
            if (Date.now() - lastActivity.current >= 600000) lock();
        }, 1000);
        const check = window.setInterval(refresh, 15000);
        return () => { events.forEach(e => window.removeEventListener(e, activity)); clearInterval(timer); clearInterval(check); };
    }, [userId, locked, mustChange, lock, refresh]);
    const role = ROLE_MAP[session?.assignments?.[activeId]?.role] || null;
    const can = React.useCallback((action) => {
        if (action === 'incident.demo_start') return !!session?.user?.permissions?.includes('incidents.create') && !!session?.user?.eligible?.includes('EL');
        if (GLOBAL_ACTIONS[action]) return !!session?.user?.permissions?.includes(GLOBAL_ACTIONS[action]);
        if (action === 'incident.close' && session?.user?.permissions?.includes('incidents.close')) return true;
        if (action.includes('delete') || action === 'incident.demo_start') return false;
        return canRole(role, action);
    }, [session, role]);
    const value = { role, roleMeta: ROLES[role], user: session?.user, userName: session?.user?.display_name || '', displayName: session?.user?.display_name || 'Benutzer', can, pickerOpen, setPickerOpen, lock, logout, refresh };
    if (loading) return <main className="p-6">Anmeldung wird geprüft …</main>;
    if (!session?.user || session.locked || session.user.must_change_password) return <IdentityGate session={session} refresh={refresh} logout={logout} />;
    return <RoleContext.Provider value={value}><React.Fragment key={JSON.stringify([session.access_version, activeId])}>{children}</React.Fragment></RoleContext.Provider>;
}
