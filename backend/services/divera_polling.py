"""One installation-wide poll, shared by automatic, manual and mapping reads.

The MongoDB lease coordinates API workers; each leased operation has a shorter
hard deadline than the lease. Retry deadlines and snapshots survive restarts.
"""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import timedelta

import httpx
from pymongo.errors import DuplicateKeyError

from core.db import db
from core.maintenance import in_maintenance
from core.time import iso, now_utc, parse_iso
from services import divera, divera_settings

logger = logging.getLogger(__name__)
_task = None
_local_lock = asyncio.Lock()
ACTIVE = {"divera_enabled": True, "status": {"$ne": "abgeschlossen"}}


class BusyError(ValueError):
    pass


@asynccontextmanager
async def operation():
    async with _local_lock:
        owner = uuid.uuid4().hex
        now = now_utc()
        try:
            result = await db.system_locks.update_one(
                {"_id": "divera", "until": {"$lte": iso(now)}},
                {"$set": {"owner": owner, "until": iso(now + timedelta(seconds=90))}},
                upsert=True,
            )
        except DuplicateKeyError:
            raise BusyError("Eine zentrale DIVERA-Abfrage läuft bereits.") from None
        if not (result.modified_count or result.upserted_id):
            raise BusyError("Eine zentrale DIVERA-Abfrage läuft bereits.")
        try:
            # Includes network, fan-out and persistence. Lease remains valid even
            # when a worker is cancelled; abandoned leases expire after a crash.
            async with asyncio.timeout(55):
                yield
        finally:
            await db.system_locks.update_one(
                {"_id": "divera", "owner": owner}, {"$set": {"until": iso(now_utc())}}
            )


def safe_error(exc):
    # Never stringify httpx errors: request URLs contain accesskey.
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code in (401, 403):
            return "DIVERA-Key ungültig oder nicht berechtigt."
        if code == 429:
            return "DIVERA-Abruflimit erreicht."
    if isinstance(exc, httpx.RequestError):
        return "DIVERA derzeit nicht erreichbar."
    return "DIVERA-Abruf fehlgeschlagen; Verbindung oder Konfiguration prüfen."


async def state():
    return await db.system_settings.find_one({"_id": "divera_poll"}) or {}


async def invalidate():
    await db.system_settings.update_one(
        {"_id": "divera_poll"},
        {"$set": {"next_at": iso(now_utc()), "snapshot": None, "failures": 0}},
        upsert=True,
    )
    ensure_task()


async def _cycle(extra_incident=None):
    if in_maintenance():
        raise BusyError("Wartungsfenster aktiv.")
    async with operation():
        config = await divera_settings.settings()
        interval = config.get("interval", 30)
        previous = await state()
        due = parse_iso(previous.get("next_at"))
        snapshot = previous.get("snapshot")
        now = now_utc()
        if due and due > now and snapshot is None:
            return {
                "ok": False,
                "matched": 0,
                "error": previous.get("error") or "Nächster Abruf ist vorgemerkt.",
                "next_at": iso(due),
            }
        if not due or due <= now:
            try:
                snapshot = await divera.fetch_vehicles()
            except Exception as exc:
                failures = min(previous.get("failures", 0) + 1, 10)
                delay = min(3600, max(interval, 10) * 2 ** (failures - 1))
                if (
                    isinstance(exc, httpx.HTTPStatusError)
                    and exc.response.status_code == 429
                ):
                    try:
                        delay = max(
                            delay,
                            min(
                                86400, int(exc.response.headers.get("Retry-After", "0"))
                            ),
                        )
                    except ValueError:
                        pass
                error = safe_error(exc)
                await db.system_settings.update_one(
                    {"_id": "divera_poll"},
                    {
                        "$set": {
                            "last_attempt_at": iso(now),
                            "error": error,
                            "failures": failures,
                            "next_at": iso(now_utc() + timedelta(seconds=delay)),
                            "snapshot": None,
                        }
                    },
                    upsert=True,
                )
                incidents = await db.incidents.find(ACTIVE, {"id": 1}).to_list(None)
                ids = {i["id"] for i in incidents}
                if extra_incident:
                    ids.add(extra_incident)
                for incident_id in ids:
                    await divera._record_poll_result(incident_id, "error", error, 0)
                return {"ok": False, "matched": 0, "error": error}
            await db.system_settings.update_one(
                {"_id": "divera_poll"},
                {
                    "$set": {
                        "last_attempt_at": iso(now),
                        "last_success_at": iso(now_utc()),
                        "error": None,
                        "failures": 0,
                        "snapshot": snapshot,
                        "next_at": iso(now_utc() + timedelta(seconds=interval)),
                    }
                },
                upsert=True,
            )
        incidents = await db.incidents.find(ACTIVE, {"id": 1}).to_list(None)
        ids = {i["id"] for i in incidents}
        if extra_incident:
            ids.add(extra_incident)
        results = {}
        for incident_id in ids:
            # Recheck after network I/O: do not update an incident stopped or
            # archived while the request was in flight.
            query = {"id": incident_id, "status": {"$ne": "abgeschlossen"}}
            if incident_id != extra_incident:
                query["divera_enabled"] = True
            if await db.incidents.find_one(query):
                results[incident_id] = await divera.apply_vehicles(
                    incident_id, snapshot
                )
        return results.get(extra_incident) or {
            "ok": True,
            "matched": sum(r["matched"] for r in results.values()),
            "vehicles_total": len(snapshot),
        }


async def sync_incident(incident_id):
    try:
        return await _cycle(incident_id)
    except BusyError:
        return {
            "ok": False,
            "matched": 0,
            "error": "Zentrale Synchronisierung läuft bereits; Status wird automatisch aktualisiert.",
        }


async def vehicles():
    # Mapping UI consumes the same cache and retry policy as the scheduler.
    result = await _cycle()
    if not result["ok"]:
        raise ValueError(result["error"])
    return (await state()).get("snapshot") or []


async def _loop():
    while True:
        try:
            if await db.incidents.find_one(ACTIVE):
                current = await state()
                due = parse_iso(current.get("next_at"))
                if not due or due <= now_utc():
                    await _cycle()
        except BusyError:
            pass
        except Exception:
            logger.warning(
                "Zentrale DIVERA-Synchronisierung unterbrochen; erneuter Versuch folgt."
            )
        await asyncio.sleep(1)


def ensure_task():
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_loop())


async def start_polling(incident_id):
    if not await divera_settings.current_key():
        raise ValueError("DIVERA-Key ist nicht konfiguriert.")
    await db.incidents.update_one(
        {"id": incident_id}, {"$set": {"divera_enabled": True}}
    )
    ensure_task()


async def stop_polling(incident_id):
    await db.incidents.update_one(
        {"id": incident_id}, {"$set": {"divera_enabled": False}}
    )


async def resume_active_pollings():
    try:
        await divera_settings.initialize()
    except (ValueError, OSError):
        logger.warning(
            "DIVERA-Key-Migration benötigt die Konfigurationsverschlüsselung."
        )
    ensure_task()


async def shutdown():
    global _task
    if _task:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None
