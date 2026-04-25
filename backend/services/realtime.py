"""In-memory realtime pub/sub for SSE notifications."""

import asyncio
from typing import Dict, Set

_SUBSCRIBERS: Set[asyncio.Queue] = set()
_PATIENT_SUBSCRIBERS: Dict[str, Set[asyncio.Queue]] = {}
_QUEUE_SIZE = 200


def subscribe_incidents() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_SIZE)
    _SUBSCRIBERS.add(q)
    return q


def unsubscribe_incidents(q: asyncio.Queue) -> None:
    _SUBSCRIBERS.discard(q)


async def publish_incident_event(event: dict) -> None:
    dead: list[asyncio.Queue] = []
    for q in list(_SUBSCRIBERS):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            # If a subscriber cannot keep up, drop oldest and retry once.
            try:
                _ = q.get_nowait()
                q.put_nowait(event)
            except Exception:
                dead.append(q)
        except Exception:
            dead.append(q)

    for q in dead:
        _SUBSCRIBERS.discard(q)


def subscribe_patients(incident_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_SIZE)
    _PATIENT_SUBSCRIBERS.setdefault(incident_id, set()).add(q)
    return q


def unsubscribe_patients(incident_id: str, q: asyncio.Queue) -> None:
    subscribers = _PATIENT_SUBSCRIBERS.get(incident_id)
    if not subscribers:
        return
    subscribers.discard(q)
    if not subscribers:
        _PATIENT_SUBSCRIBERS.pop(incident_id, None)


async def publish_patient_event(incident_id: str, event: dict) -> None:
    subscribers = _PATIENT_SUBSCRIBERS.get(incident_id)
    if not subscribers:
        return

    dead: list[asyncio.Queue] = []
    for q in list(subscribers):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            try:
                _ = q.get_nowait()
                q.put_nowait(event)
            except Exception:
                dead.append(q)
        except Exception:
            dead.append(q)

    for q in dead:
        subscribers.discard(q)
    if not subscribers:
        _PATIENT_SUBSCRIBERS.pop(incident_id, None)
