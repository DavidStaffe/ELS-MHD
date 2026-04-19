import { useEffect, useState } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import axios from "axios";

import { AppShell } from "@/components/shell/AppShell";
import Home from "@/pages/Home";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
    const [meta, setMeta] = useState(null);

    useEffect(() => {
        axios
            .get(`${API}/meta`)
            .then((r) => setMeta(r.data))
            .catch(() => setMeta(null));
    }, []);

    // Schritt 01: noch kein Incident aktiv – wird in Schritt 02 via State/Context befuellt.
    const incident = null;

    return (
        <BrowserRouter>
            <AppShell incident={incident} role="Einsatzleiter">
                <Routes>
                    <Route path="/" element={<Home meta={meta} />} />
                    <Route path="*" element={<Home meta={meta} />} />
                </Routes>
            </AppShell>
        </BrowserRouter>
    );
}

export default App;
