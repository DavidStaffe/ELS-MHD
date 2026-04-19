"""ELS MHD backend entry point.

Thin bootstrap: configure FastAPI, CORS, register routes, run migrations.
All domain logic lives under core/, models.py, routes/ and services/.
"""
import logging
import os

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from core.db import db, get_client
from routes.incidents import router as incidents_router
from routes.patients import router as patients_router
from routes.transports import router as transports_router
from routes.resources import router as resources_router
from routes.messages import router as messages_router
from routes.abschnitte import router as abschnitte_router
from routes.betten import router as betten_router
from routes.analytics import router as analytics_router


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="ELS MHD API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (
    incidents_router,
    patients_router,
    transports_router,
    resources_router,
    messages_router,
    abschnitte_router,
    betten_router,
    analytics_router,
):
    app.include_router(r)


@app.on_event("startup")
async def run_migrations():
    """One-time, idempotent migrations at boot."""
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
            await db.resources.update_one(
                {"id": r["id"]}, {"$set": {"name": new_name}}
            )
            logger.info(
                "Migration: Ressource '%s' umbenannt zu '%s'", r["name"], new_name
            )
    except Exception as exc:  # pragma: no cover
        logger.exception("Migration fehlgeschlagen: %s", exc)


@app.on_event("shutdown")
async def shutdown_db_client():
    get_client().close()
