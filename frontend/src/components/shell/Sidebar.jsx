import * as React from 'react';
import { NavLink } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { useIncidents } from '@/context/IncidentContext';
import { isPatientClosed, usePatients } from '@/context/PatientContext';
import { useTransports } from '@/context/TransportContext';
import {
  LayoutGrid,
  Activity,
  Users,
  Truck,
  Boxes,
  Radio,
  AlertOctagon,
  FileCheck2,
  Settings,
  Layers,
  Bed,
  Archive,
} from 'lucide-react';

/**
 * Sidebar – Modul-Navigation ELS MHD.
 * - Einstieg (Incident-Uebersicht) + Archiv immer verfuegbar.
 * - Lage + Module nur verfuegbar wenn aktiver Incident existiert.
 * - Bei archiviertem Incident: operative Module gesperrt (Lese-Modus).
 */
const NAV_GROUPS = (
  hasIncident,
  isArchived,
  isPlanned,
  unassignedPatientCount,
  transportBadges,
) => [
  {
    label: 'Start',
    items: [
      {
        to: '/',
        icon: LayoutGrid,
        label: 'Einstieg',
        testId: 'nav-einstieg',
        end: true,
      },
      {
        to: '/archiv',
        icon: Archive,
        label: 'Archiv',
        testId: 'nav-archiv',
      },
    ],
  },
  {
    label: isArchived ? 'Archivierter Incident' : 'Aktiver Incident',
    items: [
      {
        to: '/lage',
        icon: Activity,
        label: 'Lage',
        testId: 'nav-lage',
        disabled: !hasIncident,
        hint: hasIncident ? (isArchived ? 'lesen' : null) : 'inaktiv',
      },
      {
        to: '/patienten',
        icon: Users,
        label: 'Patienten',
        testId: 'nav-patienten',
        badge: unassignedPatientCount,
        disabled: !hasIncident || isArchived || isPlanned,
        hint: !hasIncident
          ? 'inaktiv'
          : isArchived
            ? 'gesperrt'
            : isPlanned
              ? 'geplant'
              : null,
      },
      {
        to: '/transport',
        icon: Truck,
        label: 'Transport',
        testId: 'nav-transport',
        badges: transportBadges,
        disabled: !hasIncident || isArchived || isPlanned,
        hint: !hasIncident
          ? 'inaktiv'
          : isArchived
            ? 'gesperrt'
            : isPlanned
              ? 'geplant'
              : null,
      },
      {
        to: '/ressourcen',
        icon: Boxes,
        label: 'Ressourcen',
        testId: 'nav-ressourcen',
        disabled: !hasIncident || isArchived,
        hint: !hasIncident ? 'inaktiv' : isArchived ? 'gesperrt' : null,
      },
      {
        to: '/abschnitte',
        icon: Layers,
        label: 'Abschnitte',
        testId: 'nav-abschnitte',
        disabled: !hasIncident || isArchived,
        hint: !hasIncident ? 'inaktiv' : isArchived ? 'gesperrt' : null,
      },
      {
        to: '/betten',
        icon: Bed,
        label: 'Behandlungsplaetze',
        testId: 'nav-betten',
        disabled: !hasIncident || isArchived,
        hint: !hasIncident ? 'inaktiv' : isArchived ? 'gesperrt' : null,
      },
      {
        to: '/kommunikation',
        icon: Radio,
        label: 'Funktagebuch',
        testId: 'nav-kommunikation',
        disabled: !hasIncident || isArchived,
        hint: !hasIncident ? 'inaktiv' : isArchived ? 'gesperrt' : null,
      },
      {
        to: '/konflikte',
        icon: AlertOctagon,
        label: 'Konflikte',
        testId: 'nav-konflikte',
        disabled: !hasIncident || isArchived,
        hint: !hasIncident ? 'inaktiv' : isArchived ? 'gesperrt' : null,
      },
    ],
  },
  {
    label: 'Abschluss',
    items: [
      {
        to: '/abschluss',
        icon: FileCheck2,
        label: 'Auswertung',
        testId: 'nav-abschluss',
        disabled: !hasIncident,
        hint: hasIncident ? (isArchived ? 'lesen' : null) : 'inaktiv',
      },
    ],
  },
];

export function Sidebar({ className }) {
  const { activeIncident } = useIncidents();
  const { patients } = usePatients();
  const { transports } = useTransports();
  const hasIncident = Boolean(activeIncident);
  const isArchived = activeIncident?.status === 'abgeschlossen';
  const isPlanned = activeIncident?.status === 'geplant';
  const unassignedPatientCount = React.useMemo(
    () =>
      patients.filter((p) => !isPatientClosed(p) && !p.behandlung_ressource_id)
        .length,
    [patients],
  );

  const transportBadges = React.useMemo(() => {
    // Priority order: S1 > S2 > S3 > S0 > null
    const SICHTUNG_PRIORITY = { S1: 4, S2: 3, S3: 2, S0: 1 };

    // Build a live patient sichtung lookup so recategorisation is reflected instantly
    const patientSichtungMap = new Map(patients.map((p) => [p.id, p.sichtung]));

    const sichtungClass = (group) => {
      let highest = 0;
      for (const t of group) {
        const liveSichtung = t.patient_id
          ? patientSichtungMap.get(t.patient_id)
          : t.patient_sichtung;
        const p = SICHTUNG_PRIORITY[liveSichtung] ?? 0;
        if (p > highest) highest = p;
      }
      if (highest === 4) return 'bg-red-600 text-white';
      if (highest === 3) return 'bg-amber-500 text-white';
      if (highest === 2) return 'bg-emerald-600 text-white';
      if (highest === 1) return 'bg-slate-500 text-white';
      return 'bg-slate-500 text-white';
    };

    const offeneInternList = transports.filter(
      (t) => t.status === 'offen' && t.typ === 'intern',
    );
    const offeneExternList = transports.filter(
      (t) => t.status === 'offen' && t.typ === 'extern',
    );
    return [
      {
        key: 'intern',
        label: 'Int',
        value: offeneInternList.length,
        className: sichtungClass(offeneInternList),
      },
      {
        key: 'extern',
        label: 'Ext',
        value: offeneExternList.length,
        className: sichtungClass(offeneExternList),
      },
    ];
  }, [transports, patients]);

  const groups = NAV_GROUPS(
    hasIncident,
    isArchived,
    isPlanned,
    unassignedPatientCount,
    transportBadges,
  );

  const patientBadgeClassName = React.useMemo(() => {
    if (unassignedPatientCount > 3) {
      return 'bg-red-600 text-white';
    }
    if (unassignedPatientCount >= 1) {
      return 'bg-amber-600 text-white';
    }
    return 'bg-emerald-600 text-white';
  }, [unassignedPatientCount]);

  return (
    <aside
      data-testid="app-sidebar"
      className={cn(
        'flex h-screen w-sidebar shrink-0 flex-col border-r border-border bg-surface-sunken',
        className,
      )}
    >
      {/* Logo / Marke */}
      <div className="flex h-header items-center gap-2.5 border-b border-border px-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground shadow-sm">
          <span className="font-mono text-heading font-bold">E</span>
        </div>
        <div className="min-w-0">
          <div className="text-heading leading-tight">ELS MHD</div>
          <div className="text-caption text-muted-foreground leading-tight">
            Einsatzleitsystem
          </div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto py-4">
        {groups.map((group) => (
          <div key={group.label} className="mb-4 px-3">
            <div className="mb-1.5 px-2 text-[0.7rem] uppercase tracking-wider text-muted-foreground">
              {group.label}
            </div>
            <ul className="space-y-0.5">
              {group.items.map((item) => {
                const Icon = item.icon;
                if (item.disabled) {
                  return (
                    <li key={item.to}>
                      <div
                        aria-disabled
                        data-testid={item.testId}
                        className="flex items-center gap-2.5 rounded-md px-2 py-1.5 text-body text-muted-foreground/60"
                      >
                        <Icon className="h-4 w-4" />
                        <span className="flex-1 truncate">{item.label}</span>
                        {typeof item.badge === 'number' && (
                          <span
                            data-testid={`${item.testId}-badge`}
                            className={cn(
                              'rounded-full px-1.5 py-0.5 text-[0.65rem] font-bold shadow-sm',
                              patientBadgeClassName,
                            )}
                          >
                            {item.badge}
                          </span>
                        )}
                        {Array.isArray(item.badges) &&
                          item.badges.length > 0 && (
                            <span className="ml-auto flex items-center gap-1">
                              {item.badges.map((badge) => (
                                <span
                                  key={badge.key}
                                  data-testid={`${item.testId}-badge-${badge.key}`}
                                  title={`${badge.key}: ${badge.value}`}
                                  className={cn(
                                    'rounded-full px-1.5 py-0.5 text-[0.6rem] font-bold shadow-sm',
                                    badge.className,
                                  )}
                                >
                                  {badge.label}:{badge.value}
                                </span>
                              ))}
                            </span>
                          )}
                        {item.hint && (
                          <span className="text-[0.65rem] uppercase tracking-wider text-muted-foreground/60">
                            {item.hint}
                          </span>
                        )}
                        {item.step && (
                          <span className="font-mono text-[0.65rem] text-muted-foreground/60">
                            {item.step}
                          </span>
                        )}
                      </div>
                    </li>
                  );
                }
                return (
                  <li key={item.to}>
                    <NavLink
                      to={item.to}
                      end={item.end}
                      data-testid={item.testId}
                      className={({ isActive }) =>
                        cn(
                          'flex items-center gap-2.5 rounded-md px-2 py-1.5 text-body transition-colors els-focus-ring',
                          isActive
                            ? 'bg-primary/15 text-primary'
                            : 'text-foreground/85 hover:bg-surface-raised hover:text-foreground',
                        )
                      }
                    >
                      <Icon className="h-4 w-4" />
                      <span className="truncate">{item.label}</span>
                      {typeof item.badge === 'number' && (
                        <span
                          data-testid={`${item.testId}-badge`}
                          className={cn(
                            'rounded-full px-1.5 py-0.5 text-[0.65rem] font-bold shadow-sm',
                            patientBadgeClassName,
                          )}
                        >
                          {item.badge}
                        </span>
                      )}
                      {Array.isArray(item.badges) && item.badges.length > 0 && (
                        <span className="ml-auto flex items-center gap-1">
                          {item.badges.map((badge) => (
                            <span
                              key={badge.key}
                              data-testid={`${item.testId}-badge-${badge.key}`}
                              title={`${badge.key}: ${badge.value}`}
                              className={cn(
                                'rounded-full px-1.5 py-0.5 text-[0.6rem] font-bold shadow-sm',
                                badge.className,
                              )}
                            >
                              {badge.label}:{badge.value}
                            </span>
                          ))}
                        </span>
                      )}
                    </NavLink>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="border-t border-border px-3 py-3">
        <div className="flex items-center gap-2.5 rounded-md px-2 py-1.5 text-body text-muted-foreground/70">
          <Settings className="h-4 w-4" />
          <span className="flex-1 truncate">Einstellungen</span>
          <span className="font-mono text-[0.65rem]">v0.2</span>
        </div>
      </div>
    </aside>
  );
}
