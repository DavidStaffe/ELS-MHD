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
 * Abgeleitet aus Transports: welche Ressourcen-Namen sind aktuell belegt
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
