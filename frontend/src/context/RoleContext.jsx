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
