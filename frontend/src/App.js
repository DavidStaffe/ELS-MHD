import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import { AppShell } from "@/components/shell/AppShell";
import { IncidentProvider } from "@/context/IncidentContext";
import { PatientProvider } from "@/context/PatientContext";
import { TransportProvider } from "@/context/TransportContext";
import { OpsProvider } from "@/context/OpsContext";
import { RoleProvider } from "@/context/RoleContext";
import IncidentList from "@/pages/IncidentList";
import LagePlaceholder from "@/pages/LagePlaceholder";
import PatientList from "@/pages/PatientList";
import PatientDetail from "@/pages/PatientDetail";
import TransportList from "@/pages/TransportList";
import ResourceList from "@/pages/ResourceList";
import MessageList from "@/pages/MessageList";
import KonfliktList from "@/pages/KonfliktList";
import AbschlussPage from "@/pages/AbschlussPage";

function App() {
    return (
        <BrowserRouter>
            <RoleProvider>
                <IncidentProvider>
                    <PatientProvider>
                        <TransportProvider>
                            <OpsProvider>
                                <AppShell>
                                    <Routes>
                                        <Route path="/" element={<IncidentList />} />
                                        <Route path="/lage" element={<LagePlaceholder />} />
                                        <Route path="/patienten" element={<PatientList />} />
                                        <Route path="/patienten/:patientId" element={<PatientDetail />} />
                                        <Route path="/transport" element={<TransportList />} />
                                        <Route path="/ressourcen" element={<ResourceList />} />
                                        <Route path="/kommunikation" element={<MessageList />} />
                                        <Route path="/konflikte" element={<KonfliktList />} />
                                        <Route path="/abschluss" element={<AbschlussPage />} />
                                        <Route path="*" element={<Navigate to="/" replace />} />
                                    </Routes>
                                </AppShell>
                            </OpsProvider>
                        </TransportProvider>
                    </PatientProvider>
                </IncidentProvider>
            </RoleProvider>
        </BrowserRouter>
    );
}

export default App;
