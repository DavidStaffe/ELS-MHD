import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API_BASE = `${BACKEND_URL}/api`;

export const api = axios.create({
    baseURL: API_BASE,
    timeout: 15000,
    headers: { "Content-Type": "application/json" }
});

/* =====================================================================
   Incidents
   ===================================================================== */
export async function listIncidents(params = {}) {
    const { data } = await api.get("/incidents", { params });
    return data;
}

export async function createIncident(payload) {
    const { data } = await api.post("/incidents", payload);
    return data;
}

export async function createDemoIncident() {
    const { data } = await api.post("/incidents/demo");
    return data;
}

export async function getIncident(id) {
    const { data } = await api.get(`/incidents/${id}`);
    return data;
}

export async function updateIncident(id, payload) {
    const { data } = await api.patch(`/incidents/${id}`, payload);
    return data;
}

export async function deleteIncident(id) {
    await api.delete(`/incidents/${id}`);
}
