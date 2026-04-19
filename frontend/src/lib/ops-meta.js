export const RESOURCE_STATUS = {
    verfuegbar: { label: "Verfuegbar", tone: "green" },
    im_einsatz: { label: "Im Einsatz", tone: "info" },
    wartung: { label: "Wartung", tone: "yellow" },
    offline: { label: "Offline", tone: "gray" }
};

export const RESOURCE_STATUS_KEYS = Object.keys(RESOURCE_STATUS);

export const RESOURCE_KATEGORIE = {
    uhs: { label: "UHS-Team", typ: "intern" },
    bike: { label: "Radstreife", typ: "intern" },
    rtw: { label: "RTW", typ: "extern" },
    ktw: { label: "KTW", typ: "extern" },
    nef: { label: "NEF", typ: "extern" },
    sonstiges: { label: "Sonstiges", typ: "intern" }
};

export const RESOURCE_KAT_KEYS = Object.keys(RESOURCE_KATEGORIE);

export const MESSAGE_PRIO = {
    kritisch: { label: "Kritisch", tone: "red", order: 0 },
    dringend: { label: "Dringend", tone: "yellow", order: 1 },
    normal: { label: "Normal", tone: "gray", order: 2 }
};

export const MESSAGE_KAT = {
    info: { label: "Info" },
    lage: { label: "Lage" },
    anforderung: { label: "Anforderung" },
    warnung: { label: "Warnung" }
};

export const PRIO_KEYS = Object.keys(MESSAGE_PRIO);
export const KAT_KEYS = Object.keys(MESSAGE_KAT);

export const KONFLIKT_SCHWERE = {
    rot: { label: "Kritisch", tone: "red" },
    gelb: { label: "Warnung", tone: "yellow" },
    info: { label: "Info", tone: "info" }
};
