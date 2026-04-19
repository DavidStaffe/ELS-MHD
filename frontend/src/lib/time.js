/**
 * Zeit-Helpers. Alle Datumswerte werden im Backend als ISO mit TZ gespeichert.
 */

export function formatDateTime(iso) {
    if (!iso) return "–";
    const d = new Date(iso);
    return d.toLocaleString("de-DE", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit"
    });
}

export function formatDate(iso) {
    if (!iso) return "–";
    return new Date(iso).toLocaleDateString("de-DE", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric"
    });
}

export function formatTime(d) {
    return new Date(d).toLocaleTimeString("de-DE", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
    });
}

/**
 * Formatiert Millisekunden -> HH:MM oder DD:HH:MM.
 */
export function formatDuration(ms) {
    if (ms == null || Number.isNaN(ms)) return "–";
    const sign = ms < 0 ? "-" : "";
    const total = Math.abs(Math.floor(ms / 1000));
    const days = Math.floor(total / 86400);
    const hours = Math.floor((total % 86400) / 3600);
    const mins = Math.floor((total % 3600) / 60);

    const pad = (n) => String(n).padStart(2, "0");

    if (days > 0) {
        return `${sign}${days}d ${pad(hours)}:${pad(mins)}`;
    }
    return `${sign}${pad(hours)}:${pad(mins)}`;
}

/**
 * ISO Datum fuer datetime-local Input (YYYY-MM-DDTHH:mm).
 */
export function toLocalInput(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/**
 * datetime-local Input -> ISO String (UTC).
 */
export function fromLocalInput(value) {
    if (!value) return null;
    const d = new Date(value);
    return d.toISOString();
}
