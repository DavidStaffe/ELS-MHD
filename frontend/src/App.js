import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import { AppShell } from "@/components/shell/AppShell";
import { IncidentProvider } from "@/context/IncidentContext";
import { PatientProvider } from "@/context/PatientContext";
import { TransportProvider } from "@/context/TransportContext";
import IncidentList from "@/pages/IncidentList";
import LagePlaceholder from "@/pages/LagePlaceholder";
import PatientList from "@/pages/PatientList";
import PatientDetail from "@/pages/PatientDetail";
import TransportList from "@/pages/TransportList";

function App() {
    return (
        <BrowserRouter>
            <IncidentProvider>
                <PatientProvider>
                    <TransportProvider>
                        <AppShell>
                            <Routes>
                                <Route path="/" element={<IncidentList />} />
                                <Route path="/lage" element={<LagePlaceholder />} />
                                <Route path="/patienten" element={<PatientList />} />
                                <Route path="/patienten/:patientId" element={<PatientDetail />} />
                                <Route path="/transport" element={<TransportList />} />
                                <Route path="*" element={<Navigate to="/" replace />} />
                            </Routes>
                        </AppShell>
                    </TransportProvider>
                </PatientProvider>
            </IncidentProvider>
        </BrowserRouter>
    );
}

export default App;
