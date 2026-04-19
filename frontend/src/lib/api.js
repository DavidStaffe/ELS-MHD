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

/* =====================================================================
   Patients
   ===================================================================== */
export async function listPatients(incidentId, params = {}) {
    const { data } = await api.get(`/incidents/${incidentId}/patients`, {
        params
    });
    return data;
}

export async function createPatient(incidentId, payload) {
    const { data } = await api.post(`/incidents/${incidentId}/patients`, payload);
    return data;
}

export async function getPatient(id) {
    const { data } = await api.get(`/patients/${id}`);
    return data;
}

export async function updatePatient(id, payload) {
    const { data } = await api.patch(`/patients/${id}`, payload);
    return data;
}

export async function deletePatient(id) {
    await api.delete(`/patients/${id}`);
}

/* =====================================================================
   Transports
   ===================================================================== */
export async function listTransports(incidentId, params = {}) {
    const { data } = await api.get(`/incidents/${incidentId}/transports`, {
        params
    });
    return data;
}

export async function createTransport(incidentId, payload) {
    const { data } = await api.post(`/incidents/${incidentId}/transports`, payload);
    return data;
}

export async function getTransport(id) {
    const { data } = await api.get(`/transports/${id}`);
    return data;
}

export async function updateTransport(id, payload) {
    const { data } = await api.patch(`/transports/${id}`, payload);
    return data;
}

export async function deleteTransport(id) {
    await api.delete(`/transports/${id}`);
}

/* =====================================================================
   Resources
   ===================================================================== */
export async function listResources(incidentId, params = {}) {
    const { data } = await api.get(`/incidents/${incidentId}/resources`, { params });
    return data;
}
export async function createResource(incidentId, payload) {
    const { data } = await api.post(`/incidents/${incidentId}/resources`, payload);
    return data;
}
export async function updateResource(id, payload) {
    const { data } = await api.patch(`/resources/${id}`, payload);
    return data;
}
export async function deleteResource(id) {
    await api.delete(`/resources/${id}`);
}

/* =====================================================================
   Messages
   ===================================================================== */
export async function listMessages(incidentId, params = {}) {
    const { data } = await api.get(`/incidents/${incidentId}/messages`, { params });
    return data;
}
export async function createMessage(incidentId, payload) {
    const { data } = await api.post(`/incidents/${incidentId}/messages`, payload);
    return data;
}
export async function ackMessage(id, by) {
    const { data } = await api.post(`/messages/${id}/ack`, null, { params: { by } });
    return data;
}
export async function deleteMessage(id) {
    await api.delete(`/messages/${id}`);
}

/* =====================================================================
   Konflikte (Auto-Detection)
   ===================================================================== */
export async function listKonflikte(incidentId) {
    const { data } = await api.get(`/incidents/${incidentId}/konflikte`);
    return data;
}

/* =====================================================================
   Auswertung / Abschluss / Report  (Schritt 09)
   ===================================================================== */
export async function getAuswertung(incidentId) {
    const { data } = await api.get(`/incidents/${incidentId}/auswertung`);
    return data;
}

export async function getAbschlussCheck(incidentId) {
    const { data } = await api.get(`/incidents/${incidentId}/abschluss-check`);
    return data;
}

export async function getReport(incidentId) {
    const { data } = await api.get(`/incidents/${incidentId}/report`);
    return data;
}

export async function listReportVersions(incidentId) {
    const { data } = await api.get(`/incidents/${incidentId}/report-versions`);
    return data;
}

export async function createReportVersion(incidentId, payload = {}) {
    const { data } = await api.post(
        `/incidents/${incidentId}/report-versions`,
        payload
    );
    return data;
}

export async function patchIncidentMeta(incidentId, payload) {
    const { data } = await api.patch(`/incidents/${incidentId}/meta`, payload);
    return data;
}

/* =====================================================================
   Abschnitte (Schritt 10)
   ===================================================================== */
export async function listAbschnitte(incidentId, params = {}) {
    const { data } = await api.get(`/incidents/${incidentId}/abschnitte`, { params });
    return data;
}
export async function createAbschnitt(incidentId, payload) {
    const { data } = await api.post(`/incidents/${incidentId}/abschnitte`, payload);
    return data;
}
export async function updateAbschnitt(id, payload) {
    const { data } = await api.patch(`/abschnitte/${id}`, payload);
    return data;
}
export async function deleteAbschnitt(id) {
    await api.delete(`/abschnitte/${id}`);
}

/* =====================================================================
   Behandlungsbetten (Schritt 11)
   ===================================================================== */
export async function listBetten(incidentId, params = {}) {
    const { data } = await api.get(`/incidents/${incidentId}/betten`, { params });
    return data;
}
export async function createBett(incidentId, payload) {
    const { data } = await api.post(`/incidents/${incidentId}/betten`, payload);
    return data;
}
export async function createBettenBulk(incidentId, payload) {
    const { data } = await api.post(`/incidents/${incidentId}/betten/bulk`, payload);
    return data;
}
export async function updateBett(id, payload) {
    const { data } = await api.patch(`/betten/${id}`, payload);
    return data;
}
export async function deleteBett(id) {
    await api.delete(`/betten/${id}`);
}
export async function assignBett(bettId, patientId) {
    const { data } = await api.post(`/betten/${bettId}/assign`, { patient_id: patientId });
    return data;
}
export async function releaseBett(bettId) {
    const { data } = await api.post(`/betten/${bettId}/release`);
    return data;
}
