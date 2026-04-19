export const TRANSPORT_ZIEL = {
    uhs: { label: "UHS", description: "Unfallhilfsstation" },
    krankenhaus: { label: "Krankenhaus", description: "Klinik" },
    rd: { label: "Rettungsdienst", description: "RD-Uebergabe" },
    event: { label: "Event", description: "Veranstaltung" },
    heim: { label: "Heim", description: "Nach Hause" },
    sonstiges: { label: "Sonstiges", description: "" }
};

export const ZIEL_OPTIONS = Object.keys(TRANSPORT_ZIEL);

export const TRANSPORT_STATUS = {
    offen: {
        label: "Offen",
        tone: "yellow",
        description: "Keine Ressource zugewiesen"
    },
    zugewiesen: {
        label: "Zugewiesen",
        tone: "info",
        description: "Ressource bestaetigt, noch nicht unterwegs"
    },
    unterwegs: {
        label: "Unterwegs",
        tone: "green",
        description: "Transport laeuft"
    },
    abgeschlossen: {
        label: "Abgeschlossen",
        tone: "gray",
        description: "Uebergeben / beendet"
    }
};

export const STATUS_BUCKETS = ["offen", "zugewiesen", "unterwegs", "abgeschlossen"];

/**
 * Vordefinierter Ressourcen-Pool (pro Typ).
 * In spaeteren Schritten wird Schritt 06 dies aus dem Ressourcen-Modul beziehen.
 */
export const RESOURCE_POOL = {
    intern: [
        { id: "uhs-team-1", name: "UHS Team 1", typ: "intern" },
        { id: "uhs-team-2", name: "UHS Team 2", typ: "intern" },
        { id: "uhs-team-3", name: "UHS Team 3", typ: "intern" },
        { id: "bike-1", name: "Radstreife 1", typ: "intern" }
    ],
    extern: [
        { id: "rtw-1", name: "RTW 1", typ: "extern" },
        { id: "rtw-2", name: "RTW 2", typ: "extern" },
        { id: "ktw-1", name: "KTW 1", typ: "extern" },
        { id: "ktw-2", name: "KTW 2", typ: "extern" },
        { id: "nef-1", name: "NEF 1", typ: "extern" }
    ]
};

export function resourcesForTyp(typ) {
    return RESOURCE_POOL[typ] || [];
}

/**
 * Nutzung: aus Transports ableiten, welche Ressourcen-Namen gerade belegt sind
 * (status != abgeschlossen).
 */
export function occupiedResources(transports) {
    const map = new Map();
    for (const t of transports) {
        if (!t.ressource) continue;
        if (t.status === "abgeschlossen") continue;
        if (!map.has(t.ressource)) map.set(t.ressource, []);
        map.get(t.ressource).push(t);
    }
    return map;
}
