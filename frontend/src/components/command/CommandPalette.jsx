import * as React from "react";
import { useNavigate } from "react-router-dom";
import {
    CommandDialog,
    CommandInput,
    CommandList,
    CommandEmpty,
    CommandGroup,
    CommandItem,
    CommandSeparator,
    CommandShortcut
} from "@/components/ui/command";
import {
    LayoutDashboard,
    Users,
    Truck,
    Boxes,
    Radio,
    AlertOctagon,
    FileCheck2,
    PlayCircle,
    Plus,
    Sun,
    Moon,
    Search,
    Layers,
    Bed,
    Command as CommandIcon
} from "lucide-react";

/* =====================================================================
   Command Palette – globaler ⌘K / Ctrl+K Shortcut
   API:
     const { open, registerCommand } = useCommandPalette();
     registerCommand({ id, label, group, icon, shortcut, run, keywords })
       -> gibt eine unregister()-Funktion zurueck.
   Spaetere Schritte koennen dynamische Commands (z.B. Patienten per Kennung)
   via registerCommand() einhaengen.
   ===================================================================== */

const CommandPaletteContext = React.createContext(null);

export function useCommandPalette() {
    const ctx = React.useContext(CommandPaletteContext);
    if (!ctx) {
        throw new Error(
            "useCommandPalette muss innerhalb des CommandPaletteProvider genutzt werden"
        );
    }
    return ctx;
}

const ICON_MAP = {
    einstieg: LayoutDashboard,
    patienten: Users,
    transport: Truck,
    ressourcen: Boxes,
    kommunikation: Radio,
    konflikte: AlertOctagon,
    abschluss: FileCheck2,
    demo: PlayCircle,
    neuerIncident: Plus,
    themeDark: Moon,
    themeLight: Sun,
    search: Search
};

/**
 * CommandPaletteProvider – hostet die Dialog-Instanz, registriert globale
 * Shortcuts und stellt open()/close()/registerCommand() bereit.
 */
export function CommandPaletteProvider({
    children,
    theme,
    onToggleTheme,
    onStartDemo,
    onNewIncident
}) {
    const [open, setOpen] = React.useState(false);
    const navigate = useNavigate();

    // Dynamische Commands aus Kindern
    const [dynamicCommands, setDynamicCommands] = React.useState(() => new Map());

    const registerCommand = React.useCallback((cmd) => {
        const id = cmd.id || `cmd-${Math.random().toString(36).slice(2)}`;
        setDynamicCommands((prev) => {
            const next = new Map(prev);
            next.set(id, { ...cmd, id });
            return next;
        });
        return () => {
            setDynamicCommands((prev) => {
                if (!prev.has(id)) return prev;
                const next = new Map(prev);
                next.delete(id);
                return next;
            });
        };
    }, []);

    // Globaler Shortcut: ⌘K / Ctrl+K
    React.useEffect(() => {
        const handler = (e) => {
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
                e.preventDefault();
                setOpen((prev) => !prev);
            }
            if (e.key === "Escape") {
                setOpen(false);
            }
        };
        window.addEventListener("keydown", handler);
        return () => window.removeEventListener("keydown", handler);
    }, []);

    const close = React.useCallback(() => setOpen(false), []);
    const openPalette = React.useCallback(() => setOpen(true), []);

    const runAndClose = React.useCallback(
        (fn) => () => {
            fn?.();
            setOpen(false);
        },
        []
    );

    // Standard-Commands (Schritt 02: Einstieg + Lage)
    const moduleNav = React.useMemo(
        () => [
            { id: "nav-einstieg", icon: LayoutDashboard, label: "Einstieg (Incidents)", path: "/", available: true, shortcut: "G E" },
            { id: "nav-lage", icon: ICON_MAP.patienten, label: "Lage (aktiver Incident)", path: "/lage", available: true, shortcut: "G L" },
            { id: "nav-patienten", icon: ICON_MAP.patienten, label: "Patienten", path: "/patienten", available: true, shortcut: "G P" },
            { id: "nav-transport", icon: ICON_MAP.transport, label: "Transport", path: "/transport", available: true, shortcut: "G T" },
            { id: "nav-ressourcen", icon: ICON_MAP.ressourcen, label: "Ressourcen", path: "/ressourcen", available: true, shortcut: "G R" },
            { id: "nav-abschnitte", icon: Layers, label: "Einsatzabschnitte", path: "/abschnitte", available: true, shortcut: "G S" },
            { id: "nav-betten", icon: Bed, label: "Behandlungsplaetze", path: "/betten", available: true, shortcut: "G B" },
            { id: "nav-kommunikation", icon: ICON_MAP.kommunikation, label: "Funktagebuch", path: "/kommunikation", available: true, shortcut: "G K" },
            { id: "nav-konflikte", icon: ICON_MAP.konflikte, label: "Konflikte", path: "/konflikte", available: true, shortcut: "G X" },
            { id: "nav-abschluss", icon: ICON_MAP.abschluss, label: "Auswertung & Abschluss", path: "/abschluss", available: true, shortcut: "G A" }
        ],
        []
    );

    // Gruppierte dynamische Commands
    const grouped = React.useMemo(() => {
        const map = new Map();
        for (const cmd of dynamicCommands.values()) {
            const g = cmd.group || "Aktionen";
            if (!map.has(g)) map.set(g, []);
            map.get(g).push(cmd);
        }
        return map;
    }, [dynamicCommands]);

    const value = React.useMemo(
        () => ({
            open,
            setOpen,
            openPalette,
            close,
            registerCommand
        }),
        [open, openPalette, close, registerCommand]
    );

    return (
        <CommandPaletteContext.Provider value={value}>
            {children}

            <CommandDialog
                open={open}
                onOpenChange={setOpen}
                data-testid="command-palette"
            >
                <CommandInput
                    placeholder="Modul springen, Aktion ausfuehren, Kennung suchen …"
                    data-testid="command-palette-input"
                />
                <CommandList>
                    <CommandEmpty>
                        Keine Treffer. Versuche ein anderes Stichwort.
                    </CommandEmpty>

                    {/* Dynamische Gruppen (aus registerCommand) */}
                    {Array.from(grouped.entries()).map(([groupLabel, cmds]) => (
                        <React.Fragment key={groupLabel}>
                            <CommandGroup heading={groupLabel}>
                                {cmds.map((cmd) => {
                                    const Icon = cmd.icon;
                                    return (
                                        <CommandItem
                                            key={cmd.id}
                                            value={`${cmd.label} ${(cmd.keywords || []).join(" ")}`}
                                            onSelect={runAndClose(cmd.run)}
                                            data-testid={`cmd-${cmd.id}`}
                                        >
                                            {Icon && <Icon />}
                                            <span>{cmd.label}</span>
                                            {cmd.shortcut && (
                                                <CommandShortcut>
                                                    {cmd.shortcut}
                                                </CommandShortcut>
                                            )}
                                        </CommandItem>
                                    );
                                })}
                            </CommandGroup>
                            <CommandSeparator />
                        </React.Fragment>
                    ))}

                    <CommandGroup heading="Navigation">
                        {moduleNav.map((item) => {
                            const Icon = item.icon;
                            return (
                                <CommandItem
                                    key={item.id}
                                    value={`${item.label} modul ${item.path}`}
                                    disabled={!item.available}
                                    onSelect={runAndClose(() =>
                                        item.available && navigate(item.path)
                                    )}
                                    data-testid={`cmd-${item.id}`}
                                >
                                    <Icon />
                                    <span>{item.label}</span>
                                    {!item.available && item.step && (
                                        <span className="ml-auto text-[0.7rem] font-mono text-muted-foreground">
                                            Schritt {item.step}
                                        </span>
                                    )}
                                    {item.available && item.shortcut && (
                                        <CommandShortcut>
                                            {item.shortcut}
                                        </CommandShortcut>
                                    )}
                                </CommandItem>
                            );
                        })}
                    </CommandGroup>

                    <CommandSeparator />

                    <CommandGroup heading="Incident">
                        <CommandItem
                            value="neuer incident anlegen new"
                            onSelect={runAndClose(onNewIncident)}
                            disabled={!onNewIncident}
                            data-testid="cmd-neuer-incident"
                        >
                            <Plus />
                            <span>Neuen Incident anlegen</span>
                            <CommandShortcut>N</CommandShortcut>
                        </CommandItem>
                        <CommandItem
                            value="demo incident starten vordaten"
                            onSelect={runAndClose(onStartDemo)}
                            disabled={!onStartDemo}
                            data-testid="cmd-demo-incident"
                        >
                            <PlayCircle />
                            <span>Demo-Incident starten</span>
                            <CommandShortcut>D</CommandShortcut>
                        </CommandItem>
                    </CommandGroup>

                    <CommandSeparator />

                    <CommandGroup heading="Einstellungen">
                        <CommandItem
                            value="theme wechseln dark light mode"
                            onSelect={runAndClose(onToggleTheme)}
                            data-testid="cmd-theme-toggle"
                        >
                            {theme === "light" ? <Moon /> : <Sun />}
                            <span>
                                Theme wechseln (
                                {theme === "light" ? "Dunkel" : "Hell"})
                            </span>
                            <CommandShortcut>T</CommandShortcut>
                        </CommandItem>
                    </CommandGroup>
                </CommandList>
            </CommandDialog>
        </CommandPaletteContext.Provider>
    );
}

/**
 * CommandPaletteTrigger – optionaler Button fuer Header/Topbar, zeigt
 * visuell an, dass ⌘K/Ctrl+K verfuegbar ist.
 */
export function CommandPaletteTrigger({ className }) {
    const { openPalette } = useCommandPalette();
    const isMac =
        typeof navigator !== "undefined" &&
        /Mac|iPod|iPhone|iPad/.test(navigator.platform);

    return (
        <button
            type="button"
            onClick={openPalette}
            data-testid="command-palette-trigger"
            className={
                "inline-flex items-center gap-2 rounded-md border border-border bg-surface-raised px-2.5 h-8 text-caption text-muted-foreground hover:text-foreground hover:border-primary/60 transition-colors els-focus-ring " +
                (className || "")
            }
            aria-label="Kommando-Palette oeffnen"
        >
            <Search className="h-3.5 w-3.5" />
            <span className="hidden lg:inline">Befehl oder Suche …</span>
            <kbd className="ml-1 inline-flex h-5 items-center gap-0.5 rounded bg-background px-1.5 font-mono text-[0.7rem] text-muted-foreground border border-border">
                {isMac ? (
                    <CommandIcon className="h-3 w-3" />
                ) : (
                    <span>Ctrl</span>
                )}
                <span>K</span>
            </kbd>
        </button>
    );
}
