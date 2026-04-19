/**
 * Abschnitt-Farbpalette (Schritt 10).
 * Jede Farbe wird konsistent in Sidebar, Kacheln, Ressourcen-Liste
 * und Bettansicht verwendet.
 */
export const ABSCHNITT_FARBEN = [
    { key: "red", label: "Rot", chipBg: "bg-rose-500/80", dot: "bg-rose-500", border: "border-rose-500", soft: "bg-rose-500/15 text-rose-500" },
    { key: "orange", label: "Orange", chipBg: "bg-orange-500/80", dot: "bg-orange-500", border: "border-orange-500", soft: "bg-orange-500/15 text-orange-500" },
    { key: "yellow", label: "Gelb", chipBg: "bg-amber-500/80", dot: "bg-amber-500", border: "border-amber-500", soft: "bg-amber-500/15 text-amber-500" },
    { key: "green", label: "Gruen", chipBg: "bg-emerald-500/80", dot: "bg-emerald-500", border: "border-emerald-500", soft: "bg-emerald-500/15 text-emerald-500" },
    { key: "teal", label: "Teal", chipBg: "bg-teal-500/80", dot: "bg-teal-500", border: "border-teal-500", soft: "bg-teal-500/15 text-teal-500" },
    { key: "blue", label: "Blau", chipBg: "bg-sky-500/80", dot: "bg-sky-500", border: "border-sky-500", soft: "bg-sky-500/15 text-sky-400" },
    { key: "indigo", label: "Indigo", chipBg: "bg-indigo-500/80", dot: "bg-indigo-500", border: "border-indigo-500", soft: "bg-indigo-500/15 text-indigo-400" },
    { key: "purple", label: "Violett", chipBg: "bg-violet-500/80", dot: "bg-violet-500", border: "border-violet-500", soft: "bg-violet-500/15 text-violet-400" },
    { key: "pink", label: "Pink", chipBg: "bg-pink-500/80", dot: "bg-pink-500", border: "border-pink-500", soft: "bg-pink-500/15 text-pink-400" },
    { key: "gray", label: "Grau", chipBg: "bg-slate-500/80", dot: "bg-slate-500", border: "border-slate-500", soft: "bg-slate-500/15 text-slate-400" }
];

export function getFarbe(key) {
    return ABSCHNITT_FARBEN.find((f) => f.key === key) || ABSCHNITT_FARBEN[5]; // fallback blue
}

/**
 * Bett-Typen (Schritt 11).
 */
export const BETT_TYPEN = {
    liegend: { label: "Liegend", icon: "Bed", hint: "Liegeplatz" },
    sitzend: { label: "Sitzend", icon: "Armchair", hint: "Sitzplatz" },
    schockraum: { label: "Schockraum", icon: "Zap", hint: "Schockraum / kritisch" },
    beobachtung: { label: "Beobachtung", icon: "Eye", hint: "Beobachtungsplatz" },
    sonstiges: { label: "Sonstiges", icon: "Box", hint: "Sonstiger Platz" }
};

export const BETT_STATUS = {
    frei: { label: "Frei", tone: "green" },
    belegt: { label: "Belegt", tone: "red" },
    gesperrt: { label: "Gesperrt", tone: "gray" }
};

export const BETT_TYP_KEYS = Object.keys(BETT_TYPEN);
export const BETT_STATUS_KEYS = Object.keys(BETT_STATUS);
