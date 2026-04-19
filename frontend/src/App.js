import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import { AppShell } from "@/components/shell/AppShell";
import { IncidentProvider } from "@/context/IncidentContext";
import IncidentList from "@/pages/IncidentList";
import LagePlaceholder from "@/pages/LagePlaceholder";

function App() {
    return (
        <BrowserRouter>
            <IncidentProvider>
                <AppShell>
                    <Routes>
                        <Route path="/" element={<IncidentList />} />
                        <Route path="/lage" element={<LagePlaceholder />} />
                        <Route path="*" element={<Navigate to="/" replace />} />
                    </Routes>
                </AppShell>
            </IncidentProvider>
        </BrowserRouter>
    );
}

export default App;
