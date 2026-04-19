import * as React from "react";
import { Sidebar } from "./Sidebar";
import { GlobalHeader } from "./GlobalHeader";
import { cn } from "@/lib/utils";
import { CommandPaletteProvider } from "@/components/command/CommandPalette";

const THEME_KEY = "els-theme";

function applyTheme(theme) {
    const root = document.documentElement;
    root.classList.remove("light", "dark");
    root.classList.add(theme);
}

export function AppShell({
    children,
    incident,
    role = "Einsatzleiter",
    onStartDemo,
    onNewIncident
}) {
    const [theme, setTheme] = React.useState(() => {
        if (typeof window === "undefined") return "dark";
        return localStorage.getItem(THEME_KEY) || "dark";
    });

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

    return (
        <CommandPaletteProvider
            theme={theme}
            onToggleTheme={toggleTheme}
            onStartDemo={onStartDemo}
            onNewIncident={onNewIncident}
        >
            <div className={cn("flex h-screen w-full bg-background text-foreground")}>
                <Sidebar />
                <div className="flex min-w-0 flex-1 flex-col">
                    <GlobalHeader
                        incident={incident}
                        role={role}
                        theme={theme}
                        onToggleTheme={toggleTheme}
                    />
                    <main
                        data-testid="app-main"
                        className="flex-1 overflow-y-auto"
                    >
                        {children}
                    </main>
                </div>
            </div>
        </CommandPaletteProvider>
    );
}
