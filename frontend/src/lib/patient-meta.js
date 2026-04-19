export const SICHTUNG = [
    { key: "S1", label: "S1", tone: "red", hint: "Sofort / kritisch", shortcut: "1" },
    { key: "S2", label: "S2", tone: "yellow", hint: "Dringend", shortcut: "2" },
    { key: "S3", label: "S3", tone: "green", hint: "Normal", shortcut: "3" },
    { key: "S0", label: "S0", tone: "gray", hint: "Leicht / Abwartend", shortcut: "0" }
];

export const SICHTUNG_KEYS = SICHTUNG.map((s) => s.key);

export const PATIENT_STATUS = {
    wartend: { label: "Wartend", tone: "yellow" },
    in_behandlung: { label: "In Behandlung", tone: "info" },
    transportbereit: { label: "Transportbereit", tone: "green" },
    uebergeben: { label: "Uebergeben", tone: "gray" },
    entlassen: { label: "Entlassen", tone: "gray" }
};

export const PATIENT_VERBLEIB = {
    unbekannt: "Unbekannt",
    uhs: "UHS",
    rd: "Rettungsdienst",
    krankenhaus: "Krankenhaus",
    event: "Event",
    heim: "Heim",
    sonstiges: "Sonstiges"
};

export const TRANSPORT_TYP = {
    intern: { label: "Intern", tone: "info", description: "UHS / eigene Ressource" },
    extern: { label: "Extern", tone: "yellow", description: "Rettungsdienst / KH" }
};

export const FALLABSCHLUSS_TYP = {
    rd_uebergabe: {
        label: "RD-Uebergabe",
        tone: "info",
        description: "Uebergabe an Rettungsdienst"
    },
    entlassung: {
        label: "Entlassung",
        tone: "green",
        description: "Entlassung in Veranstaltung"
    },
    manuell: {
        label: "Manuell",
        tone: "gray",
        description: "Sonstiger Abschluss"
    }
};

export const STATUS_OPTIONS = Object.keys(PATIENT_STATUS);
export const VERBLEIB_OPTIONS = Object.keys(PATIENT_VERBLEIB);

/**
 * Liefert den naechsten logischen Status fuer Ein-Klick-Progression.
 * null = keine weitere Aktion moeglich.
 */
export function nextProgression(patient) {
    if (!patient) return null;
    if (patient.status === "wartend") {
        if (!patient.sichtung)
            return {
                type: "require-sichtung",
                label: "Sichtung waehlen",
                description: "Eine Sichtungsstufe vergeben startet die Behandlung."
            };
        return {
            type: "set-status",
            payload: { status: "in_behandlung" },
            label: "Behandlung starten",
            description: "Status -> In Behandlung"
        };
    }
    if (patient.status === "in_behandlung") {
        return {
            type: "ask-transport",
            label: "Transport anfordern",
            description: "Intern (UHS) oder extern (RD)"
        };
    }
    if (patient.status === "transportbereit") {
        return {
            type: "ask-fallabschluss",
            label: "Fall abschliessen",
            description: "RD-Uebergabe / Entlassung / Manuell"
        };
    }
    return null; // uebergeben / entlassen: Ende
}
