import * as React from "react";
import {
    listPatients as apiList,
    createPatient as apiCreate,
    updatePatient as apiUpdate,
    deletePatient as apiDelete
} from "@/lib/api";
import { useIncidents } from "@/context/IncidentContext";

const PatientContext = React.createContext(null);

export function usePatients() {
    const ctx = React.useContext(PatientContext);
    if (!ctx) {
        throw new Error(
            "usePatients muss innerhalb des PatientProvider verwendet werden"
        );
    }
    return ctx;
}

export function PatientProvider({ children }) {
    const { activeIncident } = useIncidents();
    const [patients, setPatients] = React.useState([]);
    const [loading, setLoading] = React.useState(false);
    const [error, setError] = React.useState(null);

    const incidentId = activeIncident?.id || null;

    const refresh = React.useCallback(async () => {
        if (!incidentId) {
            setPatients([]);
            return [];
        }
        setLoading(true);
        setError(null);
        try {
            const data = await apiList(incidentId);
            setPatients(data);
            return data;
        } catch (e) {
            setError(e?.message || "Fehler beim Laden der Patienten");
            return [];
        } finally {
            setLoading(false);
        }
    }, [incidentId]);

    // Auto-Refresh bei Incident-Wechsel
    React.useEffect(() => {
        refresh();
    }, [refresh]);

    const create = React.useCallback(
        async (payload) => {
            if (!incidentId) throw new Error("Kein aktiver Incident");
            const created = await apiCreate(incidentId, payload);
            setPatients((prev) => [...prev, created]);
            return created;
        },
        [incidentId]
    );

    const update = React.useCallback(async (id, payload) => {
        const updated = await apiUpdate(id, payload);
        setPatients((prev) =>
            prev.map((p) => (p.id === id ? updated : p))
        );
        return updated;
    }, []);

    const remove = React.useCallback(async (id) => {
        await apiDelete(id);
        setPatients((prev) => prev.filter((p) => p.id !== id));
    }, []);

    // Abgeleitete KPIs
    const kpis = React.useMemo(() => {
        const buckets = { total: patients.length, S1: 0, S2: 0, S3: 0, S0: 0, wartend: 0, behandlung: 0, transport: 0, abgeschlossen: 0 };
        for (const p of patients) {
            if (p.sichtung && buckets[p.sichtung] !== undefined) buckets[p.sichtung]++;
            if (p.status === "wartend") buckets.wartend++;
            else if (p.status === "in_behandlung") buckets.behandlung++;
            else if (p.status === "transportbereit") buckets.transport++;
            else if (p.status === "uebergeben" || p.status === "entlassen") buckets.abgeschlossen++;
        }
        return buckets;
    }, [patients]);

    const value = React.useMemo(
        () => ({
            patients,
            loading,
            error,
            incidentId,
            refresh,
            create,
            update,
            remove,
            kpis
        }),
        [patients, loading, error, incidentId, refresh, create, update, remove, kpis]
    );

    return (
        <PatientContext.Provider value={value}>
            {children}
        </PatientContext.Provider>
    );
}
