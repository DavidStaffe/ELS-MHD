"""ELS MHD backend entry point.

Thin bootstrap: configure FastAPI, CORS, register routes, run migrations.
All domain logic lives under core/, models.py, routes/ and services/.
"""

import logging
import os

from fastapi import FastAPI, Depends
from core.access import authorize
from core.body_limit import RequestBodyLimit
from core.identity import indexes
from routes.identity import router as identity_router
from routes.governance import router as governance_router
from fastapi.exceptions import RequestValidationError
from starlette.middleware.cors import CORSMiddleware

from core.db import db, get_client
from core.maintenance import in_maintenance
from fastapi.responses import JSONResponse
from core.validation import validation_error
from routes.incidents import router as incidents_router
from routes.patients import router as patients_router
from routes.transports import router as transports_router
from routes.resources import router as resources_router
from routes.messages import router as messages_router
from routes.abschnitte import router as abschnitte_router
from routes.betten import router as betten_router
from routes.analytics import router as analytics_router
from routes.divera import router as divera_router
from routes.patient_disposition import router as patient_disposition_router
from routes.keywords import router as keywords_router
from routes.system_updates import router as system_updates_router
from services import divera_polling as divera_service
from core.admin import router as admin_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="ELS MHD API", version="1.0.0", dependencies=[Depends(authorize)])
app.add_exception_handler(RequestValidationError, validation_error)


@app.middleware("http")
async def management_no_store(request, call_next):
    if (
        in_maintenance()
        and not request.url.path.startswith(("/api/system/updates/", "/api/admin/"))
        and request.url.path != "/api/meta"
        and request.url.path not in {"/api/auth/me", "/api/auth/login", "/api/auth/logout", "/api/auth/lock", "/api/auth/unlock", "/api/auth/reauth"}
    ):
        return JSONResponse(
            status_code=503,
            content={"detail": "Wartung läuft. Bitte warten."},
            headers={"Retry-After": "5"},
        )
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    if request.url.path.startswith(
        ("/api/admin/", "/api/divera/settings", "/api/system/updates")
    ):
        response.headers["Cache-Control"] = "no-store"
    return response


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip() and o.strip() != "*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestBodyLimit)

for r in (
    identity_router,
    governance_router,
    incidents_router,
    patients_router,
    transports_router,
    resources_router,
    messages_router,
    abschnitte_router,
    betten_router,
    analytics_router,
    divera_router,
    patient_disposition_router,
    keywords_router,
    system_updates_router,
    admin_router,
):
    app.include_router(r)


@app.on_event("startup")
async def run_migrations():
    """One-time, idempotent migrations at boot."""
    await indexes()  # Fail startup closed if the identity database is unavailable.
    if in_maintenance():
        return  # Web releases must be schema-compatible; migrations require SSH.
    try:
        result = await db.patients.update_many(
            {"sichtung": "S4"}, {"$set": {"sichtung": "S0"}}
        )
        if result.modified_count:
            logger.info(
                "Migration: %d Patient(en) von S4 nach S0 umbenannt",
                result.modified_count,
            )
        # Ressourcen-Kategorie "bike" -> "evt" (Radstreife -> EVT)
        bike_cat = await db.resources.update_many(
            {"kategorie": "bike"}, {"$set": {"kategorie": "evt"}}
        )
        if bike_cat.modified_count:
            logger.info(
                "Migration: %d Ressource(n) von Kategorie 'bike' nach 'evt' umbenannt",
                bike_cat.modified_count,
            )
        # Default-Ressourcen-Namen "Radstreife N" -> "EVT N"
        async for r in db.resources.find(
            {"name": {"$regex": "^Radstreife "}}, {"_id": 0, "id": 1, "name": 1}
        ):
            new_name = r["name"].replace("Radstreife ", "EVT ", 1)
            await db.resources.update_one({"id": r["id"]}, {"$set": {"name": new_name}})
            logger.info(
                "Migration: Ressource '%s' umbenannt zu '%s'", r["name"], new_name
            )
    except Exception as exc:  # pragma: no cover
        logger.exception("Migration fehlgeschlagen: %s", exc)


@app.on_event("startup")
async def resume_divera_polling():
    """Re-attach Divera-Polling tasks for incidents that had it enabled."""
    try:
        await divera_service.resume_active_pollings()
    except Exception as exc:  # pragma: no cover
        logger.warning("Divera-Resume fehlgeschlagen: %s", exc)


@app.on_event("shutdown")
async def shutdown_db_client():
    await divera_service.shutdown()
    get_client().close()
