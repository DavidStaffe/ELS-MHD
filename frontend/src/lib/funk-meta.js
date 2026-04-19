/**
 * Funktagebuch-Metadaten (Schritt 13).
 */
export const FUNK_TYPEN = {
    funk_ein: { label: "Funk eingehend", icon: "RadioReceiver", tone: "info", short: "FE" },
    funk_aus: { label: "Funk ausgehend", icon: "Send", tone: "info", short: "FA" },
    lage: { label: "Lagemeldung", icon: "MapPin", tone: "yellow", short: "L" },
    auftrag: { label: "Auftrag / Weisung", icon: "ClipboardList", tone: "red", short: "A" },
    rueckmeldung: { label: "Rueckmeldung", icon: "CheckCircle", tone: "green", short: "R" },
    vorkommnis: { label: "Besonderes Vorkommnis", icon: "AlertOctagon", tone: "red", short: "V" },
    system: { label: "Systemeintrag", icon: "Cpu", tone: "gray", short: "S" }
};

export const FUNK_TYP_KEYS = Object.keys(FUNK_TYPEN);

export const FUNK_PRIO = {
    kritisch: { label: "Kritisch", tone: "red" },
    dringend: { label: "Dringend", tone: "yellow" },
    normal: { label: "Normal", tone: "green" }
};

export function fmtTime(iso) {
    if (!iso) return "–";
    try {
        const d = new Date(iso);
        return d.toLocaleTimeString("de-DE", {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit"
        });
    } catch {
        return iso;
    }
}

export function fmtDateTime(iso) {
    if (!iso) return "–";
    try {
        const d = new Date(iso);
        return d.toLocaleString("de-DE", {
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit"
        });
    } catch {
        return iso;
    }
}
