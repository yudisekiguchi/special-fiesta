"""Servidor web local. Rode com:  uvicorn app.main:app --port 8000"""
from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .adapters import ADAPTERS
from .adapters.base import USER_AGENT
from .models import MediaType
from .scoring import merge_duplicates, score

STATIC = Path(__file__).parent / "static"
LEVEL_ORDER = {"green": 0, "yellow": 1, "red": 2}

app = FastAPI(title="Busca Segura de Torrents")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/sources")
def sources():
    return [{"id": k, "name": v.name} for k, v in ADAPTERS.items()]


@app.get("/api/search")
async def search(
    q: str = Query(..., min_length=2, max_length=200),
    media: MediaType | None = None,
    sources: str | None = Query(None, description="ids separados por vírgula"),
    hide_red: bool = False,
):
    chosen = [s for s in (sources.split(",") if sources else ADAPTERS) if s in ADAPTERS]
    if not chosen:
        raise HTTPException(400, "Nenhuma fonte válida")

    async with httpx.AsyncClient(timeout=15, follow_redirects=True,
                                 headers={"User-Agent": USER_AGENT}) as client:
        tasks = [ADAPTERS[s](client).search(q, media) for s in chosen]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)

    results, errors = [], []
    for sid, out in zip(chosen, outcomes):
        if isinstance(out, Exception):
            errors.append({"source": ADAPTERS[sid].name, "error": str(out) or type(out).__name__})
        else:
            results.extend(out)

    results = [score(r) for r in merge_duplicates(results)]
    if hide_red:
        results = [r for r in results if r.level != "red"]
    results.sort(key=lambda r: (LEVEL_ORDER[r.level], -r.score, -(r.seeders or 0)))
    return {"query": q, "count": len(results), "errors": errors,
            "results": [r.to_dict() for r in results]}
