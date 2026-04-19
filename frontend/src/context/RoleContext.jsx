import * as React from "react";

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
    "incident.delete": ["einsatzleiter"],
    "incident.close": ["einsatzleiter"],
    "incident.demo_start": ["einsatzleiter", "helfer", "dokumentar"],

    // Patienten
    "patient.create": ["einsatzleiter", "helfer"],
    "patient.update": ["einsatzleiter", "helfer"],
    "patient.delete": ["einsatzleiter"],
    "patient.progress": ["einsatzleiter", "helfer"],

    // Transport
    "transport.create": ["einsatzleiter"],
    "transport.assign": ["einsatzleiter", "helfer"],
    "transport.status": ["einsatzleiter", "helfer"],
    "transport.delete": ["einsatzleiter"],

    // Ressourcen
    "resource.update": ["einsatzleiter"],
    "resource.create": ["einsatzleiter"],
    "resource.delete": ["einsatzleiter"],

    // Kommunikation
    "message.create": ["einsatzleiter", "helfer"],
    "message.ack": ["einsatzleiter", "helfer"],
    "message.delete": ["einsatzleiter"],

    // Konflikte
    "konflikt.resolve": ["einsatzleiter", "helfer"],

    // Abschluss
    "abschluss.view": ["einsatzleiter", "dokumentar"],
    "abschluss.freigabe": ["einsatzleiter"],
    "abschluss.export_pdf": ["einsatzleiter", "dokumentar"],
    "abschluss.edit_meta": ["einsatzleiter", "dokumentar"],
    "abschluss.version_create": ["einsatzleiter"]
};

export function canRole(role, action) {
    const allowed = PERMS[action];
    if (!allowed) return true; // unbekannte Aktion = erlaubt
    return role ? allowed.includes(role) : false;
}

const RoleContext = React.createContext(null);
const ROLE_KEY = "els-role";

export function useRole() {
    const ctx = React.useContext(RoleContext);
    if (!ctx) throw new Error("useRole muss innerhalb des RoleProvider genutzt werden");
    return ctx;
}

export function RoleProvider({ children }) {
    const [role, setRole] = React.useState(() => {
        if (typeof window === "undefined") return null;
        return localStorage.getItem(ROLE_KEY) || null;
    });
    const [pickerOpen, setPickerOpen] = React.useState(false);

    React.useEffect(() => {
        if (!role) setPickerOpen(true);
    }, [role]);

    const setAndPersist = React.useCallback((r) => {
        setRole(r);
        try {
            if (r) localStorage.setItem(ROLE_KEY, r);
            else localStorage.removeItem(ROLE_KEY);
        } catch {
            /* noop */
        }
    }, []);

    const can = React.useCallback(
        (action) => canRole(role, action),
        [role]
    );

    const value = React.useMemo(
        () => ({
            role,
            roleMeta: role ? ROLES[role] : null,
            setRole: setAndPersist,
            can,
            pickerOpen,
            setPickerOpen
        }),
        [role, setAndPersist, can, pickerOpen]
    );

    return <RoleContext.Provider value={value}>{children}</RoleContext.Provider>;
}
