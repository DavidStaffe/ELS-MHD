import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import { AppShell } from "@/components/shell/AppShell";
import { IncidentProvider } from "@/context/IncidentContext";
import { PatientProvider } from "@/context/PatientContext";
import IncidentList from "@/pages/IncidentList";
import LagePlaceholder from "@/pages/LagePlaceholder";
import PatientList from "@/pages/PatientList";

function App() {
    return (
        <BrowserRouter>
            <IncidentProvider>
                <PatientProvider>
                    <AppShell>
                        <Routes>
                            <Route path="/" element={<IncidentList />} />
                            <Route path="/lage" element={<LagePlaceholder />} />
                            <Route path="/patienten" element={<PatientList />} />
                            <Route path="*" element={<Navigate to="/" replace />} />
                        </Routes>
                    </AppShell>
                </PatientProvider>
            </IncidentProvider>
        </BrowserRouter>
    );
}

export default App;
