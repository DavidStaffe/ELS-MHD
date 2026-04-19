/** @type {import('tailwindcss').Config} */
module.exports = {
    darkMode: ["class"],
    content: [
        "./src/**/*.{js,jsx,ts,tsx}",
        "./public/index.html"
    ],
    theme: {
        extend: {
            fontFamily: {
                sans: ["IBM Plex Sans", "ui-sans-serif", "system-ui", "sans-serif"],
                mono: ["IBM Plex Mono", "ui-monospace", "SFMono-Regular", "monospace"]
            },
            fontSize: {
                caption: ["0.8rem", { lineHeight: "1.35" }],
                body: ["0.9rem", { lineHeight: "1.45" }],
                heading: ["1rem", { lineHeight: "1.3", fontWeight: "600" }],
                display: ["1.25rem", { lineHeight: "1.2", fontWeight: "600" }],
                kpi: ["1.75rem", { lineHeight: "1.1", fontWeight: "600" }]
            },
            borderRadius: {
                lg: "var(--radius-lg)",
                md: "var(--radius)",
                sm: "var(--radius-sm)"
            },
            colors: {
                background: "hsl(var(--background))",
                foreground: "hsl(var(--foreground))",
                card: {
                    DEFAULT: "hsl(var(--card))",
                    foreground: "hsl(var(--card-foreground))"
                },
                popover: {
                    DEFAULT: "hsl(var(--popover))",
                    foreground: "hsl(var(--popover-foreground))"
                },
                surface: {
                    raised: "hsl(var(--surface-raised))",
                    sunken: "hsl(var(--surface-sunken))"
                },
                primary: {
                    DEFAULT: "hsl(var(--primary))",
                    foreground: "hsl(var(--primary-foreground))"
                },
                secondary: {
                    DEFAULT: "hsl(var(--secondary))",
                    foreground: "hsl(var(--secondary-foreground))"
                },
                muted: {
                    DEFAULT: "hsl(var(--muted))",
                    foreground: "hsl(var(--muted-foreground))"
                },
                accent: {
                    DEFAULT: "hsl(var(--accent))",
                    foreground: "hsl(var(--accent-foreground))"
                },
                destructive: {
                    DEFAULT: "hsl(var(--destructive))",
                    foreground: "hsl(var(--destructive-foreground))"
                },
                border: "hsl(var(--border))",
                input: "hsl(var(--input))",
                ring: "hsl(var(--ring))",
                status: {
                    red: {
                        DEFAULT: "hsl(var(--status-red))",
                        fg: "hsl(var(--status-red-fg))"
                    },
                    yellow: {
                        DEFAULT: "hsl(var(--status-yellow))",
                        fg: "hsl(var(--status-yellow-fg))"
                    },
                    green: {
                        DEFAULT: "hsl(var(--status-green))",
                        fg: "hsl(var(--status-green-fg))"
                    },
                    gray: {
                        DEFAULT: "hsl(var(--status-gray))",
                        fg: "hsl(var(--status-gray-fg))"
                    },
                    info: {
                        DEFAULT: "hsl(var(--status-info))",
                        fg: "hsl(var(--status-info-fg))"
                    }
                },
                chart: {
                    1: "hsl(var(--chart-1))",
                    2: "hsl(var(--chart-2))",
                    3: "hsl(var(--chart-3))",
                    4: "hsl(var(--chart-4))",
                    5: "hsl(var(--chart-5))"
                }
            },
            spacing: {
                // 4px Raster (Tailwind nutzt 0.25rem = 4px) – explizite Aliases
                "header": "var(--header-h)",
                "sidebar": "var(--sidebar-w)"
            },
            keyframes: {
                "accordion-down": {
                    from: { height: "0" },
                    to: { height: "var(--radix-accordion-content-height)" }
                },
                "accordion-up": {
                    from: { height: "var(--radix-accordion-content-height)" },
                    to: { height: "0" }
                },
                "pulse-ring": {
                    "0%, 100%": { opacity: "0.45" },
                    "50%": { opacity: "1" }
                }
            },
            animation: {
                "accordion-down": "accordion-down 0.2s ease-out",
                "accordion-up": "accordion-up 0.2s ease-out",
                "pulse-ring": "pulse-ring 1.8s ease-in-out infinite"
            }
        }
    },
    plugins: [require("tailwindcss-animate")]
};
