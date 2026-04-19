import { useEffect, useState, useCallback } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import axios from "axios";

import { AppShell } from "@/components/shell/AppShell";
import Home from "@/pages/Home";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function AppInner() {
    const [meta, setMeta] = useState(null);
    const [demoOpen, setDemoOpen] = useState(false);
    const [newOpen, setNewOpen] = useState(false);

    useEffect(() => {
        axios
            .get(`${API}/meta`)
            .then((r) => setMeta(r.data))
            .catch(() => setMeta(null));
    }, []);

    const startDemo = useCallback(() => setDemoOpen(true), []);
    const newIncident = useCallback(() => setNewOpen(true), []);

    // Schritt 01: noch kein Incident aktiv – wird in Schritt 02 via State/Context befuellt.
    const incident = null;

    return (
        <AppShell
            incident={incident}
            role="Einsatzleiter"
            onStartDemo={startDemo}
            onNewIncident={newIncident}
        >
            <Routes>
                <Route
                    path="/"
                    element={
                        <Home
                            meta={meta}
                            demoOpen={demoOpen}
                            setDemoOpen={setDemoOpen}
                            newOpen={newOpen}
                            setNewOpen={setNewOpen}
                        />
                    }
                />
                <Route
                    path="*"
                    element={
                        <Home
                            meta={meta}
                            demoOpen={demoOpen}
                            setDemoOpen={setDemoOpen}
                            newOpen={newOpen}
                            setNewOpen={setNewOpen}
                        />
                    }
                />
            </Routes>
        </AppShell>
    );
}

function App() {
    return (
        <BrowserRouter>
            <AppInner />
        </BrowserRouter>
    );
}

export default App;
