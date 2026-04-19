import * as React from "react";
import { useNavigate } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { GlobalHeader } from "./GlobalHeader";
import { RoleSelectorDialog } from "./RoleSelector";
import { cn } from "@/lib/utils";
import {
    CommandPaletteProvider,
    useCommandPalette
} from "@/components/command/CommandPalette";
import { NewIncidentDialog } from "@/components/incidents/NewIncidentDialog";
import { useIncidents } from "@/context/IncidentContext";
import { useRole } from "@/context/RoleContext";

const THEME_KEY = "els-theme";

function applyTheme(theme) {
    const root = document.documentElement;
    root.classList.remove("light", "dark");
    root.classList.add(theme);
}

function RoleCommandRegistrar() {
    const { registerCommand } = useCommandPalette();
    const { setPickerOpen } = useRole();
    React.useEffect(() => {
        return registerCommand({
            id: "role-change",
            label: "Rolle wechseln",
            group: "Einstellungen",
            run: () => setPickerOpen(true)
        });
    }, [registerCommand, setPickerOpen]);
    return null;
}

export function AppShell({ children }) {
    const [theme, setTheme] = React.useState(() => {
        if (typeof window === "undefined") return "dark";
        return localStorage.getItem(THEME_KEY) || "dark";
    });
    const [newOpen, setNewOpen] = React.useState(false);
    const navigate = useNavigate();

    const { activeIncident, create, startDemo, setActive } = useIncidents();
    const { can } = useRole();

    React.useEffect(() => {
        applyTheme(theme);
        try {
            localStorage.setItem(THEME_KEY, theme);
        } catch {
            /* noop */
        }
    }, [theme]);

    const toggleTheme = React.useCallback(() => {
        setTheme((t) => (t === "dark" ? "light" : "dark"));
    }, []);

    const handleStartDemo = React.useCallback(async () => {
        try {
            const created = await startDemo();
            setActive(created.id);
            navigate("/lage");
        } catch (e) {
            console.error("Demo start failed:", e);
        }
    }, [startDemo, setActive, navigate]);

    const handleNewIncident = React.useCallback(() => setNewOpen(true), []);

    return (
        <CommandPaletteProvider
            theme={theme}
            onToggleTheme={toggleTheme}
            onStartDemo={can("incident.demo_start") ? handleStartDemo : undefined}
            onNewIncident={can("incident.create") ? handleNewIncident : undefined}
        >
            <RoleCommandRegistrar />
            <div className={cn("flex h-screen w-full bg-background text-foreground")}>
                <Sidebar />
                <div className="flex min-w-0 flex-1 flex-col">
                    <GlobalHeader
                        incident={activeIncident}
                        theme={theme}
                        onToggleTheme={toggleTheme}
                        onGoToIncidents={() => navigate("/")}
                    />
                    <main
                        data-testid="app-main"
                        className="flex-1 overflow-y-auto"
                    >
                        {children}
                    </main>
                </div>
            </div>

            <RoleSelectorDialog />

            <NewIncidentDialog
                open={newOpen}
                onOpenChange={setNewOpen}
                onCreate={async (payload) => {
                    const created = await create(payload);
                    setActive(created.id);
                    navigate("/lage");
                }}
            />
        </CommandPaletteProvider>
    );
}
