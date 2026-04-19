import * as React from "react";
import {
    listIncidents as apiList,
    createIncident as apiCreate,
    createDemoIncident as apiDemo,
    updateIncident as apiUpdate,
    deleteIncident as apiDelete
} from "@/lib/api";

const ACTIVE_KEY = "els-active-incident";

const IncidentContext = React.createContext(null);

export function useIncidents() {
    const ctx = React.useContext(IncidentContext);
    if (!ctx) {
        throw new Error("useIncidents muss innerhalb des IncidentProvider verwendet werden");
    }
    return ctx;
}

export function IncidentProvider({ children }) {
    const [incidents, setIncidents] = React.useState([]);
    const [loading, setLoading] = React.useState(true);
    const [error, setError] = React.useState(null);
    const [activeId, setActiveId] = React.useState(() => {
        if (typeof window === "undefined") return null;
        return localStorage.getItem(ACTIVE_KEY) || null;
    });

    const persistActive = React.useCallback((id) => {
        setActiveId(id);
        try {
            if (id) localStorage.setItem(ACTIVE_KEY, id);
            else localStorage.removeItem(ACTIVE_KEY);
        } catch {
            /* noop */
        }
    }, []);

    const refresh = React.useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await apiList();
            setIncidents(data);
            return data;
        } catch (e) {
            setError(e?.message || "Fehler beim Laden der Incidents");
            return [];
        } finally {
            setLoading(false);
        }
    }, []);

    React.useEffect(() => {
        refresh();
    }, [refresh]);

    // Ungueltige activeId bereinigen sobald Liste geladen
    React.useEffect(() => {
        if (!activeId) return;
        if (loading) return;
        if (!incidents.some((i) => i.id === activeId)) {
            persistActive(null);
        }
    }, [activeId, incidents, loading, persistActive]);

    const create = React.useCallback(
        async (payload, { autoActivate = true } = {}) => {
            const created = await apiCreate(payload);
            setIncidents((prev) => [created, ...prev]);
            if (autoActivate) persistActive(created.id);
            return created;
        },
        [persistActive]
    );

    const startDemo = React.useCallback(
        async ({ autoActivate = true } = {}) => {
            const created = await apiDemo();
            setIncidents((prev) => [created, ...prev]);
            if (autoActivate) persistActive(created.id);
            return created;
        },
        [persistActive]
    );

    const update = React.useCallback(async (id, payload) => {
        const updated = await apiUpdate(id, payload);
        setIncidents((prev) => prev.map((i) => (i.id === id ? updated : i)));
        return updated;
    }, []);

    const remove = React.useCallback(
        async (id) => {
            await apiDelete(id);
            setIncidents((prev) => prev.filter((i) => i.id !== id));
            if (activeId === id) persistActive(null);
        },
        [activeId, persistActive]
    );

    const closeIncident = React.useCallback(
        (id) => update(id, { status: "abgeschlossen" }),
        [update]
    );

    const reopenIncident = React.useCallback(
        (id) => update(id, { status: "operativ", end_at: null }),
        [update]
    );

    const activeIncident = React.useMemo(
        () => incidents.find((i) => i.id === activeId) || null,
        [incidents, activeId]
    );

    const value = React.useMemo(
        () => ({
            incidents,
            loading,
            error,
            activeId,
            activeIncident,
            setActive: persistActive,
            refresh,
            create,
            startDemo,
            update,
            closeIncident,
            reopenIncident,
            remove
        }),
        [
            incidents,
            loading,
            error,
            activeId,
            activeIncident,
            persistActive,
            refresh,
            create,
            startDemo,
            update,
            closeIncident,
            reopenIncident,
            remove
        ]
    );

    return (
        <IncidentContext.Provider value={value}>
            {children}
        </IncidentContext.Provider>
    );
}
