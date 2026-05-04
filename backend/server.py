"""ELS MHD backend entry point.

Thin bootstrap: configure FastAPI, CORS, register routes, run migrations.
All domain logic lives under core/, models/, routes/ and services/.
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
from routes.auth import router as auth_router
from routes.users import router as users_router
from routes.incident_roles import router as incident_roles_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="ELS MHD API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (
    auth_router,
    users_router,
    incident_roles_router,
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
        await db.users.create_index("username", unique=True)
        await db.users.create_index("id", unique=True)
        await db.incident_roles.create_index(
            [("user_id", 1), ("incident_id", 1)], unique=True
        )
        await db.incident_roles.create_index("id", unique=True)
        # Refresh tokens expire after 7 days via TTL index
        await db.refresh_tokens.create_index("created_at", expireAfterSeconds=604800)
        # Index for fast revocation lookup
        await db.refresh_tokens.create_index("token_hash", unique=True)

        result = await db.patients.update_many(
            {"sichtung": "S4"}, {"$set": {"sichtung": "S0"}}
        )
        if result.modified_count:
            logger.info(
                "Migration: %d Patient(en) von S4 nach S0 umbenannt", result.modified_count
            )

        bike_cat = await db.resources.update_many(
            {"kategorie": "bike"}, {"$set": {"kategorie": "evt"}}
        )
        if bike_cat.modified_count:
            logger.info(
                "Migration: %d Ressource(n) von 'bike' nach 'evt' umbenannt",
                bike_cat.modified_count,
            )

        async for r in db.resources.find(
            {"name": {"$regex": "^Radstreife "}}, {"_id": 0, "id": 1, "name": 1}
        ):
            new_name = r["name"].replace("Radstreife ", "EVT ", 1)
            await db.resources.update_one(
                {"id": r["id"]}, {"$set": {"name": new_name}}
            )
            logger.info("Migration: '%s' → '%s'", r["name"], new_name)

    except Exception as exc:
        logger.exception("Migration fehlgeschlagen: %s", exc)


@app.on_event("shutdown")
async def shutdown_db_client():
    get_client().close()
