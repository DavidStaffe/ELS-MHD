"""Keywords (Stichwort-Katalog) routes."""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException

from core.db import db
from core.time import iso, now_utc
from models import Keyword, KeywordCreate, KeywordUpdate

router = APIRouter(prefix="/api", tags=["keywords"])

@router.get("/keywords", response_model=List[dict])
async def list_keywords(active: Optional[bool] = None):
    query = {}
    if active is not None:
        query["active"] = active
    return await db.keywords.find(query, {"_id": 0}).sort("sort_order", 1).to_list(1000)

@router.post("/keywords", response_model=dict, status_code=201)
async def create_keyword(payload: KeywordCreate):
    kw = Keyword(**payload.model_dump(exclude_none=True))
    d = kw.model_dump()
    for k in ("created_at", "updated_at"):
        if isinstance(d.get(k), datetime):
            d[k] = iso(d[k])
    await db.keywords.insert_one(d)
    return {k: v for k, v in d.items() if k != "_id"}

@router.get("/keywords/{keyword_id}", response_model=dict)
async def get_keyword(keyword_id: str):
    d = await db.keywords.find_one({"id": keyword_id}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Stichwort nicht gefunden")
    return d

@router.patch("/keywords/{keyword_id}", response_model=dict)
async def update_keyword(keyword_id: str, payload: KeywordUpdate):
    upd = payload.model_dump(exclude_none=True)
    if not upd:
        raise HTTPException(status_code=400, detail="Keine Aenderungen")
    upd["updated_at"] = iso(now_utc())
    
    res = await db.keywords.find_one_and_update(
        {"id": keyword_id}, {"$set": upd},
        return_document=True, projection={"_id": 0}
    )
    if not res:
        raise HTTPException(status_code=404, detail="Stichwort nicht gefunden")
    return res

@router.delete("/keywords/{keyword_id}", status_code=204)
async def delete_keyword(keyword_id: str):
    res = await db.keywords.delete_one({"id": keyword_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Stichwort nicht gefunden")
    return None
