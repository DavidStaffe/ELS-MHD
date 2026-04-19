export const SICHTUNG = [
    { key: "S1", label: "S1", tone: "red", hint: "Sofort / kritisch" },
    { key: "S2", label: "S2", tone: "yellow", hint: "Dringend" },
    { key: "S3", label: "S3", tone: "green", hint: "Normal" },
    { key: "S4", label: "S4", tone: "gray", hint: "Leicht / Abwartend" }
];

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

export const STATUS_OPTIONS = Object.keys(PATIENT_STATUS);
export const VERBLEIB_OPTIONS = Object.keys(PATIENT_VERBLEIB);
