import * as React from "react";
import {
    listResources, updateResource, createResource, deleteResource,
    listMessages, createMessage, ackMessage, deleteMessage,
    listKonflikte
} from "@/lib/api";
import { useIncidents } from "@/context/IncidentContext";

const OpsContext = React.createContext(null);

export function useOps() {
    const ctx = React.useContext(OpsContext);
    if (!ctx) throw new Error("useOps muss innerhalb des OpsProvider genutzt werden");
    return ctx;
}

export function OpsProvider({ children }) {
    const { activeIncident } = useIncidents();
    const incidentId = activeIncident?.id || null;

    const [resources, setResources] = React.useState([]);
    const [messages, setMessages] = React.useState([]);
    const [konflikte, setKonflikte] = React.useState([]);
    const [loading, setLoading] = React.useState(false);

    const refreshResources = React.useCallback(async () => {
        if (!incidentId) {
            setResources([]);
            return [];
        }
        try {
            const d = await listResources(incidentId);
            setResources(d);
            return d;
        } catch {
            return [];
        }
    }, [incidentId]);

    const refreshMessages = React.useCallback(async () => {
        if (!incidentId) {
            setMessages([]);
            return [];
        }
        try {
            const d = await listMessages(incidentId);
            setMessages(d);
            return d;
        } catch {
            return [];
        }
    }, [incidentId]);

    const refreshKonflikte = React.useCallback(async () => {
        if (!incidentId) {
            setKonflikte([]);
            return [];
        }
        try {
            const d = await listKonflikte(incidentId);
            setKonflikte(d);
            return d;
        } catch {
            return [];
        }
    }, [incidentId]);

    const refreshAll = React.useCallback(async () => {
        setLoading(true);
        try {
            await Promise.all([refreshResources(), refreshMessages(), refreshKonflikte()]);
        } finally {
            setLoading(false);
        }
    }, [refreshResources, refreshMessages, refreshKonflikte]);

    React.useEffect(() => {
        refreshAll();
    }, [refreshAll]);

    // Auto-Poll Konflikte alle 30s
    React.useEffect(() => {
        if (!incidentId) return undefined;
        const id = setInterval(refreshKonflikte, 30000);
        return () => clearInterval(id);
    }, [incidentId, refreshKonflikte]);

    // ---- Resource mutations ----
    const updResource = React.useCallback(async (id, payload) => {
        const u = await updateResource(id, payload);
        setResources(prev => prev.map(r => r.id === id ? u : r));
        return u;
    }, []);
    const addResource = React.useCallback(async (payload) => {
        if (!incidentId) throw new Error("Kein aktiver Incident");
        const c = await createResource(incidentId, payload);
        setResources(prev => [...prev, c]);
        return c;
    }, [incidentId]);
    const rmResource = React.useCallback(async (id) => {
        await deleteResource(id);
        setResources(prev => prev.filter(r => r.id !== id));
    }, []);

    // ---- Message mutations ----
    const addMessage = React.useCallback(async (payload) => {
        if (!incidentId) throw new Error("Kein aktiver Incident");
        const c = await createMessage(incidentId, payload);
        setMessages(prev => [c, ...prev]);
        refreshKonflikte();
        return c;
    }, [incidentId, refreshKonflikte]);
    const ackMsg = React.useCallback(async (id, by = "Einsatzleiter") => {
        const u = await ackMessage(id, by);
        setMessages(prev => prev.map(m => m.id === id ? u : m));
        refreshKonflikte();
        return u;
    }, [refreshKonflikte]);
    const rmMessage = React.useCallback(async (id) => {
        await deleteMessage(id);
        setMessages(prev => prev.filter(m => m.id !== id));
        refreshKonflikte();
    }, [refreshKonflikte]);

    const value = React.useMemo(() => ({
        incidentId, loading,
        resources, refreshResources, updResource, addResource, rmResource,
        messages, refreshMessages, addMessage, ackMsg, rmMessage,
        konflikte, refreshKonflikte, refreshAll
    }), [
        incidentId, loading,
        resources, refreshResources, updResource, addResource, rmResource,
        messages, refreshMessages, addMessage, ackMsg, rmMessage,
        konflikte, refreshKonflikte, refreshAll
    ]);

    return <OpsContext.Provider value={value}>{children}</OpsContext.Provider>;
}
