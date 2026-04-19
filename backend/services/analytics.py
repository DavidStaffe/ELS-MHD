"""Analytics services: konflikte auto-detection, auswertung, abschluss-check, report."""
from fastapi import HTTPException

from core.db import db
from core.time import iso, now_utc, parse_iso, _duration_ms, _avg_minutes


# --------------------------------------------------------------------------
# Konflikte (Auto-Detection)
# --------------------------------------------------------------------------

async def detect_konflikte(incident_id: str) -> list[dict]:
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")

    now = now_utc()
    konflikte: list[dict] = []

    # Regel 1: S1-Patient wartend > 5 Min
    patients = await db.patients.find(
        {"incident_id": incident_id, "status": "wartend", "sichtung": "S1"},
        {"_id": 0},
    ).to_list(500)
    for p in patients:
        created = parse_iso(p.get("created_at"))
        if created and (now - created).total_seconds() > 300:
            konflikte.append({
                "id": f"p-wartend-{p['id']}",
                "typ": "patient_kritisch_wartet",
                "schwere": "rot",
                "titel": f"S1-Patient wartet ({p['kennung']})",
                "beschreibung": f"S1-Patient {p['kennung']} ist seit {int((now - created).total_seconds() // 60)} Min. im Status 'wartend'.",
                "bezug_typ": "patient",
                "bezug_id": p["id"],
                "bezug_label": p["kennung"],
                "seit": iso(created),
            })

    # Regel 2: Transport offen ohne Ressource > 10 Min
    tnow = await db.transports.find(
        {"incident_id": incident_id, "status": "offen", "ressource": None},
        {"_id": 0},
    ).to_list(500)
    for t in tnow:
        created = parse_iso(t.get("created_at"))
        if created and (now - created).total_seconds() > 600:
            konflikte.append({
                "id": f"t-offen-{t['id']}",
                "typ": "transport_ohne_ressource",
                "schwere": "gelb",
                "titel": "Transport ohne Ressource",
                "beschreibung": f"Transport {t.get('patient_kennung') or 'ohne Patient'} wartet seit {int((now - created).total_seconds() // 60)} Min. auf eine Ressource.",
                "bezug_typ": "transport",
                "bezug_id": t["id"],
                "bezug_label": t.get("patient_kennung") or "Transport",
                "seit": iso(created),
            })

    # Regel 3: Transport unterwegs > 60 Min
    tunterwegs = await db.transports.find(
        {"incident_id": incident_id, "status": "unterwegs"},
        {"_id": 0},
    ).to_list(500)
    for t in tunterwegs:
        start = parse_iso(t.get("gestartet_at"))
        if start and (now - start).total_seconds() > 3600:
            konflikte.append({
                "id": f"t-lang-{t['id']}",
                "typ": "transport_lang_unterwegs",
                "schwere": "gelb",
                "titel": "Transport lange unterwegs",
                "beschreibung": f"Transport {t.get('patient_kennung') or ''} ({t.get('ressource') or 'unbekannt'}) bereits {int((now - start).total_seconds() // 60)} Min. unterwegs.",
                "bezug_typ": "transport",
                "bezug_id": t["id"],
                "bezug_label": t.get("patient_kennung") or "Transport",
                "seit": iso(start),
            })

    # Regel 4: Kritische Meldungen unquittiert
    mhigh = await db.messages.find(
        {"incident_id": incident_id, "prioritaet": "kritisch", "quittiert_at": None},
        {"_id": 0},
    ).to_list(200)
    for m in mhigh:
        konflikte.append({
            "id": f"m-unack-{m['id']}",
            "typ": "kritische_meldung_offen",
            "schwere": "rot",
            "titel": "Kritische Meldung unquittiert",
            "beschreibung": m["text"][:160],
            "bezug_typ": "message",
            "bezug_id": m["id"],
            "bezug_label": m.get("von") or "System",
            "seit": m.get("created_at"),
        })

    order = {"rot": 0, "gelb": 1, "info": 2}
    konflikte.sort(key=lambda k: order.get(k["schwere"], 9))
    return konflikte


# --------------------------------------------------------------------------
# Auswertung
# --------------------------------------------------------------------------

async def get_auswertung(incident_id: str) -> dict:
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")

    patients = await db.patients.find({"incident_id": incident_id}, {"_id": 0}).to_list(2000)
    transports = await db.transports.find({"incident_id": incident_id}, {"_id": 0}).to_list(2000)
    messages = await db.messages.find({"incident_id": incident_id}, {"_id": 0}).to_list(2000)
    resources = await db.resources.find({"incident_id": incident_id}, {"_id": 0}).to_list(500)
    abschnitte = await db.abschnitte.find({"incident_id": incident_id}, {"_id": 0}).to_list(200)
    betten = await db.betten.find({"incident_id": incident_id}, {"_id": 0}).to_list(500)

    # A Patienten
    sichtung_counts = {"S1": 0, "S2": 0, "S3": 0, "S0": 0, "ohne": 0}
    status_counts = {k: 0 for k in ["wartend", "in_behandlung", "transportbereit", "uebergeben", "entlassen"]}
    wartezeiten = []
    behandlungsdauern = []
    for p in patients:
        if p.get("sichtung") in sichtung_counts:
            sichtung_counts[p["sichtung"]] += 1
        else:
            sichtung_counts["ohne"] += 1
        st = p.get("status")
        if st in status_counts:
            status_counts[st] += 1
        wartezeiten.append(_duration_ms(p.get("created_at"), p.get("sichtung_at")))
        behandlungsdauern.append(_duration_ms(p.get("behandlung_start_at"), p.get("fallabschluss_at")))

    block_a = {
        "total": len(patients),
        "sichtung": sichtung_counts,
        "status": status_counts,
        "wartezeit_min_avg": _avg_minutes(wartezeiten),
        "behandlungsdauer_min_avg": _avg_minutes(behandlungsdauern),
    }

    # Bett-KPIs
    bett_belegt = [b for b in betten if b.get("status") == "belegt"]
    bett_belegungsdauern = []
    now_dt = now_utc()
    for b in betten:
        if b.get("belegt_seit"):
            bett_belegungsdauern.append(_duration_ms(b["belegt_seit"], iso(now_dt)))
    total_betten = len(betten)
    auslastung = round(100.0 * len(bett_belegt) / total_betten, 1) if total_betten else 0.0
    block_a["betten"] = {
        "total": total_betten,
        "frei": sum(1 for b in betten if b.get("status") == "frei"),
        "belegt": len(bett_belegt),
        "gesperrt": sum(1 for b in betten if b.get("status") == "gesperrt"),
        "auslastung_pct": auslastung,
        "belegungsdauer_min_avg": _avg_minutes(bett_belegungsdauern),
        "max_gleichzeitig": len(bett_belegt),
    }

    # B Transporte
    t_by_status = {"offen": 0, "zugewiesen": 0, "unterwegs": 0, "abgeschlossen": 0}
    t_by_typ = {"intern": 0, "extern": 0}
    t_dauern = []
    for t in transports:
        if t.get("status") in t_by_status:
            t_by_status[t["status"]] += 1
        if t.get("typ") in t_by_typ:
            t_by_typ[t["typ"]] += 1
        t_dauern.append(_duration_ms(t.get("gestartet_at"), t.get("abgeschlossen_at")))
    block_b = {
        "total": len(transports),
        "status": t_by_status,
        "typ": t_by_typ,
        "fahrtdauer_min_avg": _avg_minutes(t_dauern),
    }

    # C Meldungen
    m_prio = {"kritisch": 0, "dringend": 0, "normal": 0}
    m_offen = 0
    ack_dauern = []
    for m in messages:
        if m.get("prioritaet") in m_prio:
            m_prio[m["prioritaet"]] += 1
        if not m.get("quittiert_at"):
            m_offen += 1
        ack_dauern.append(_duration_ms(m.get("created_at"), m.get("quittiert_at")))
    block_c = {
        "total": len(messages),
        "prioritaet": m_prio,
        "offen": m_offen,
        "quittier_dauer_min_avg": _avg_minutes(ack_dauern),
    }

    # D Ressourcen
    r_status = {"verfuegbar": 0, "im_einsatz": 0, "wartung": 0, "offline": 0}
    for r in resources:
        if r.get("status") in r_status:
            r_status[r["status"]] += 1
    ohne_abschnitt = [r for r in resources if not r.get("abschnitt_id")]
    block_d = {
        "total": len(resources),
        "status": r_status,
        "ohne_abschnitt": len(ohne_abschnitt),
        "ohne_abschnitt_pct": round(100.0 * len(ohne_abschnitt) / len(resources), 1) if resources else 0.0,
    }

    # G Abschnitte
    abschnitte_summary = []
    for a in abschnitte:
        a_res = [r for r in resources if r.get("abschnitt_id") == a["id"]]
        a_bet = [b for b in betten if b.get("abschnitt_id") == a["id"]]
        im_einsatz = sum(1 for r in a_res if r.get("status") == "im_einsatz")
        belegt_count = sum(1 for b in a_bet if b.get("status") == "belegt")
        if not a_res:
            ampel = "gray"
        elif im_einsatz == len(a_res):
            ampel = "red"
        elif im_einsatz > 0:
            ampel = "yellow"
        else:
            ampel = "green"
        abschnitte_summary.append({
            "id": a["id"], "name": a["name"],
            "farbe": a.get("farbe", "blue"),
            "aktiv": a.get("aktiv", True),
            "ressourcen_total": len(a_res),
            "ressourcen_im_einsatz": im_einsatz,
            "betten_total": len(a_bet),
            "betten_belegt": belegt_count,
            "ampel": ampel,
        })
    block_g = {
        "total": len(abschnitte),
        "aktiv": sum(1 for a in abschnitte if a.get("aktiv", True)),
        "abschnitte": abschnitte_summary,
    }

    # E Konflikte
    konflikte = await detect_konflikte(incident_id)
    block_e = {
        "total": len(konflikte),
        "rot": sum(1 for k in konflikte if k["schwere"] == "rot"),
        "gelb": sum(1 for k in konflikte if k["schwere"] == "gelb"),
    }

    # F Metadaten
    end_ref = inc.get("end_at") or iso(now_utc())
    dauer_ms = _duration_ms(inc.get("start_at"), end_ref)
    block_f = {
        "incident_id": inc["id"], "name": inc["name"],
        "typ": inc.get("typ"), "ort": inc.get("ort"),
        "status": inc.get("status"), "demo": bool(inc.get("demo")),
        "start_at": inc.get("start_at"), "end_at": inc.get("end_at"),
        "einsatzdauer_min": round((dauer_ms or 0) / 1000 / 60, 1),
    }

    return {
        "A_patienten": block_a, "B_transporte": block_b, "C_kommunikation": block_c,
        "D_ressourcen": block_d, "E_konflikte": block_e, "F_metadaten": block_f,
        "G_abschnitte": block_g,
    }


# --------------------------------------------------------------------------
# Abschluss-Check
# --------------------------------------------------------------------------

async def get_abschluss_check(incident_id: str) -> dict:
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")

    patients = await db.patients.find({"incident_id": incident_id}, {"_id": 0}).to_list(2000)
    transports = await db.transports.find({"incident_id": incident_id}, {"_id": 0}).to_list(2000)
    messages = await db.messages.find({"incident_id": incident_id}, {"_id": 0}).to_list(2000)
    resources = await db.resources.find({"incident_id": incident_id}, {"_id": 0}).to_list(500)
    abschnitte = await db.abschnitte.find({"incident_id": incident_id}, {"_id": 0}).to_list(200)
    betten = await db.betten.find({"incident_id": incident_id}, {"_id": 0}).to_list(500)

    blockers: list[dict] = []
    warnings: list[dict] = []

    offene = [p for p in patients if p.get("status") in ("wartend", "in_behandlung", "transportbereit")]
    if offene:
        blockers.append({
            "id": "offene_patienten",
            "titel": f"{len(offene)} offene Patienten",
            "beschreibung": "Alle Patienten muessen abgeschlossen (uebergeben oder entlassen) sein.",
            "typ": "patienten", "count": len(offene),
        })

    unterwegs = [t for t in transports if t.get("status") in ("offen", "zugewiesen", "unterwegs")]
    if unterwegs:
        blockers.append({
            "id": "offene_transporte",
            "titel": f"{len(unterwegs)} offene Transporte",
            "beschreibung": "Alle Transporte muessen abgeschlossen sein.",
            "typ": "transporte", "count": len(unterwegs),
        })

    krit = [m for m in messages if m.get("prioritaet") == "kritisch" and not m.get("quittiert_at")]
    if krit:
        blockers.append({
            "id": "offene_kritisch",
            "titel": f"{len(krit)} kritische Meldungen unquittiert",
            "beschreibung": "Kritische Meldungen muessen vor Abschluss quittiert sein.",
            "typ": "meldungen", "count": len(krit),
        })

    drng = [m for m in messages if m.get("prioritaet") == "dringend" and not m.get("quittiert_at")]
    if drng:
        warnings.append({
            "id": "offene_dringend",
            "titel": f"{len(drng)} dringende Meldungen unquittiert",
            "beschreibung": "Empfehlung: vor Abschluss quittieren.",
            "typ": "meldungen", "count": len(drng),
        })

    ohne_s = [p for p in patients if not p.get("sichtung")]
    if ohne_s:
        warnings.append({
            "id": "ohne_sichtung",
            "titel": f"{len(ohne_s)} Patienten ohne Sichtung",
            "beschreibung": "Sichtung nachtragen fuer vollstaendigen Bericht.",
            "typ": "patienten", "count": len(ohne_s),
        })

    if not messages:
        warnings.append({
            "id": "keine_meldungen",
            "titel": "Keine Meldungen erfasst",
            "beschreibung": "Fuer vollstaendige Dokumentation sollten Meldungen erfasst sein.",
            "typ": "meldungen", "count": 0,
        })

    # Schritt 12: aktive Patienten ohne Bett/Transport
    transport_patient_ids = {t.get("patient_id") for t in transports if t.get("patient_id")}
    aktiv = []
    for p in patients:
        if p.get("status") in ("in_behandlung", "transportbereit"):
            if not p.get("bett_id") and p.get("id") not in transport_patient_ids:
                aktiv.append(p)
    if aktiv:
        blockers.append({
            "id": "aktive_ohne_bett_transport",
            "titel": f"{len(aktiv)} aktive Patienten ohne Bett und ohne Transport",
            "beschreibung": "Aktiver Patient muss einem Bett zugewiesen oder in Transport sein.",
            "typ": "patienten", "count": len(aktiv),
        })

    # Schritt 10: Ressourcen ohne Abschnitt > 20%
    if resources:
        ohne_a = [r for r in resources if not r.get("abschnitt_id")]
        pct = 100.0 * len(ohne_a) / len(resources)
        if pct > 20:
            warnings.append({
                "id": "ressourcen_ohne_abschnitt",
                "titel": f"{len(ohne_a)} Ressourcen ohne Abschnitt ({pct:.0f}%)",
                "beschreibung": "Empfehlung: Ressourcen einem Einsatzabschnitt zuweisen.",
                "typ": "ressourcen", "count": len(ohne_a),
            })

    leere = [a for a in abschnitte if not any(r.get("abschnitt_id") == a["id"] for r in resources)]
    if leere:
        warnings.append({
            "id": "abschnitte_leer",
            "titel": f"{len(leere)} Abschnitte ohne Ressourcen",
            "beschreibung": "Diese Abschnitte haben keine zugeordneten Ressourcen: "
                            + ", ".join(a["name"] for a in leere[:3])
                            + ("…" if len(leere) > 3 else ""),
            "typ": "abschnitte", "count": len(leere),
        })

    nie_belegt = [b for b in betten if not b.get("belegt_seit") and b.get("status") == "gesperrt"]
    if nie_belegt:
        warnings.append({
            "id": "betten_nie_belegt",
            "titel": f"{len(nie_belegt)} Betten gesperrt und nie belegt",
            "beschreibung": "Diese Betten wurden wahrscheinlich nicht benoetigt.",
            "typ": "betten", "count": len(nie_belegt),
        })

    return {
        "incident_status": inc.get("status"),
        "bereit_fuer_abschluss": len(blockers) == 0,
        "blockers": blockers,
        "warnings": warnings,
    }


# --------------------------------------------------------------------------
# Report (14 Kapitel)
# --------------------------------------------------------------------------

async def get_report(incident_id: str) -> dict:
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")

    auswertung = await get_auswertung(incident_id)
    patients = await db.patients.find({"incident_id": incident_id}, {"_id": 0}).sort("kennung", 1).to_list(2000)
    transports = await db.transports.find({"incident_id": incident_id}, {"_id": 0}).sort("created_at", 1).to_list(2000)
    messages = await db.messages.find({"incident_id": incident_id}, {"_id": 0}).sort("created_at", 1).to_list(2000)
    resources = await db.resources.find({"incident_id": incident_id}, {"_id": 0}).to_list(500)
    abschnitte = await db.abschnitte.find({"incident_id": incident_id}, {"_id": 0}).to_list(200)
    betten = await db.betten.find({"incident_id": incident_id}, {"_id": 0}).to_list(500)

    kapitel = [
        {"nr": 1, "titel": "Einsatzgrunddaten", "inhalt": {
            "name": inc["name"], "typ": inc.get("typ"), "ort": inc.get("ort"),
            "start": inc.get("start_at"), "ende": inc.get("end_at"),
            "dauer_min": auswertung["F_metadaten"]["einsatzdauer_min"],
            "demo": inc.get("demo", False),
        }},
        {"nr": 2, "titel": "Organisation & Rollen", "inhalt": {
            "einsatzleiter": "Einsatzleiter (Rolle)",
            "rollen": ["Einsatzleiter", "Sanitaeter / Helfer", "Dokumentar"],
            "abschnitte": [
                {"id": a["id"], "name": a["name"], "farbe": a.get("farbe", "blue"), "aktiv": a.get("aktiv", True)}
                for a in abschnitte
            ],
        }},
        {"nr": 3, "titel": "Patientenuebersicht", "inhalt": auswertung["A_patienten"]},
        {"nr": 4, "titel": "Patientenliste", "inhalt": {"patienten": patients}},
        {"nr": 5, "titel": "Sichtungsverteilung", "inhalt": auswertung["A_patienten"]["sichtung"]},
        {"nr": 6, "titel": "Behandlungszeiten", "inhalt": {
            "wartezeit_min_avg": auswertung["A_patienten"]["wartezeit_min_avg"],
            "behandlungsdauer_min_avg": auswertung["A_patienten"]["behandlungsdauer_min_avg"],
        }},
        {"nr": 7, "titel": "Transporte", "inhalt": {
            "transporte": transports, "summary": auswertung["B_transporte"]
        }},
        {"nr": 8, "titel": "Ressourcen", "inhalt": {
            "ressourcen": resources, "summary": auswertung["D_ressourcen"],
            "abschnitte": auswertung["G_abschnitte"],
            "betten": auswertung["A_patienten"].get("betten", {}),
            "bettliste": betten,
        }},
        {"nr": 9, "titel": "Kommunikation", "inhalt": {
            "meldungen": messages, "summary": auswertung["C_kommunikation"]
        }},
        {"nr": 10, "titel": "Konflikte & Blocker", "inhalt": auswertung["E_konflikte"]},
        {"nr": 11, "titel": "Besondere Vorkommnisse", "inhalt": {
            "text": inc.get("meta", {}).get("besondere_vorkommnisse", "Keine besonderen Vorkommnisse dokumentiert."),
        }},
        {"nr": 12, "titel": "Nachbearbeitung & Anmerkungen", "inhalt": {
            "text": inc.get("meta", {}).get("nachbearbeitung", ""),
        }},
        {"nr": 13, "titel": "Freigabe", "inhalt": {
            "bereit_fuer_abschluss": inc.get("status") == "abgeschlossen",
            "freigegeben_von": inc.get("meta", {}).get("freigegeben_von"),
            "freigabe_at": inc.get("meta", {}).get("freigabe_at"),
        }},
        {"nr": 14, "titel": "Anhaenge & Quellen", "inhalt": {
            "quellen": "Generiert aus ELS-MHD Systemdaten.",
            "generiert_at": iso(now_utc()),
        }},
    ]

    return {"incident": inc, "kapitel": kapitel, "generiert_at": iso(now_utc())}
