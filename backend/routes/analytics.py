"""Analytics routes: konflikte, auswertung, abschluss-check, report, report-versions."""
import uuid
from typing import List

from fastapi import APIRouter, HTTPException

from core.db import db
from core.time import iso, now_utc
from models import ReportVersionCreate
from services.analytics import (
    detect_konflikte,
    get_auswertung,
    get_abschluss_check,
    get_report,
)

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/incidents/{incident_id}/konflikte", response_model=List[dict])
async def konflikte_endpoint(incident_id: str):
    return await detect_konflikte(incident_id)


@router.get("/incidents/{incident_id}/auswertung", response_model=dict)
async def auswertung_endpoint(incident_id: str):
    return await get_auswertung(incident_id)


@router.get("/incidents/{incident_id}/abschluss-check", response_model=dict)
async def abschluss_check_endpoint(incident_id: str):
    return await get_abschluss_check(incident_id)


@router.get("/incidents/{incident_id}/report", response_model=dict)
async def report_endpoint(incident_id: str):
    return await get_report(incident_id)


@router.get("/incidents/{incident_id}/report-versions", response_model=List[dict])
async def list_report_versions(incident_id: str):
    return await db.report_versions.find(
        {"incident_id": incident_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)


@router.post("/incidents/{incident_id}/report-versions", response_model=dict, status_code=201)
async def create_report_version(incident_id: str, payload: ReportVersionCreate):
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident nicht gefunden")
    count = await db.report_versions.count_documents({"incident_id": incident_id})
    report = await get_report(incident_id)
    doc = {
        "id": str(uuid.uuid4()),
        "incident_id": incident_id,
        "version": count + 1,
        "freigegeben_von": payload.freigegeben_von or "Einsatzleiter",
        "kommentar": payload.kommentar or "",
        "snapshot": report,
        "created_at": iso(now_utc()),
    }
    await db.report_versions.insert_one(doc)
    await db.incidents.update_one(
        {"id": incident_id},
        {"$set": {
            "meta.freigegeben_von": doc["freigegeben_von"],
            "meta.freigabe_at": doc["created_at"],
            "updated_at": iso(now_utc()),
        }},
    )
    return {k: v for k, v in doc.items() if k != "_id"}
