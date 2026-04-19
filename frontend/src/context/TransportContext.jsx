import * as React from "react";
import {
    listTransports as apiList,
    createTransport as apiCreate,
    updateTransport as apiUpdate,
    deleteTransport as apiDelete
} from "@/lib/api";
import { useIncidents } from "@/context/IncidentContext";

const TransportContext = React.createContext(null);

export function useTransports() {
    const ctx = React.useContext(TransportContext);
    if (!ctx) {
        throw new Error(
            "useTransports muss innerhalb des TransportProvider verwendet werden"
        );
    }
    return ctx;
}

export function TransportProvider({ children }) {
    const { activeIncident } = useIncidents();
    const [transports, setTransports] = React.useState([]);
    const [loading, setLoading] = React.useState(false);
    const [error, setError] = React.useState(null);
    const incidentId = activeIncident?.id || null;

    const refresh = React.useCallback(async () => {
        if (!incidentId) {
            setTransports([]);
            return [];
        }
        setLoading(true);
        setError(null);
        try {
            const data = await apiList(incidentId);
            setTransports(data);
            return data;
        } catch (e) {
            setError(e?.message || "Fehler beim Laden der Transporte");
            return [];
        } finally {
            setLoading(false);
        }
    }, [incidentId]);

    React.useEffect(() => {
        refresh();
    }, [refresh]);

    // Automatisch refreshen, wenn Patienten-Transport-Typ sich aendert (Polling-Ersatz)
    // Wird via expliziter Triggering-Funktion getriggert.

    const create = React.useCallback(
        async (payload) => {
            if (!incidentId) throw new Error("Kein aktiver Incident");
            const created = await apiCreate(incidentId, payload);
            setTransports((prev) => [...prev, created]);
            return created;
        },
        [incidentId]
    );

    const update = React.useCallback(async (id, payload) => {
        const updated = await apiUpdate(id, payload);
        setTransports((prev) => prev.map((t) => (t.id === id ? updated : t)));
        return updated;
    }, []);

    const remove = React.useCallback(async (id) => {
        await apiDelete(id);
        setTransports((prev) => prev.filter((t) => t.id !== id));
    }, []);

    const kpis = React.useMemo(() => {
        const b = { total: transports.length, offen: 0, zugewiesen: 0, unterwegs: 0, abgeschlossen: 0, intern: 0, extern: 0 };
        for (const t of transports) {
            if (b[t.status] !== undefined) b[t.status]++;
            if (b[t.typ] !== undefined) b[t.typ]++;
        }
        return b;
    }, [transports]);

    const value = React.useMemo(
        () => ({
            transports,
            loading,
            error,
            incidentId,
            refresh,
            create,
            update,
            remove,
            kpis
        }),
        [transports, loading, error, incidentId, refresh, create, update, remove, kpis]
    );

    return (
        <TransportContext.Provider value={value}>
            {children}
        </TransportContext.Provider>
    );
}
