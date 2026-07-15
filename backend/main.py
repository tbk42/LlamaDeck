from __future__ import annotations

import argparse
import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.database import init_db
from backend.routers import instances, models, import_gguf, pull, gguf_library, credentials, tasks


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="LlamaDeck", lifespan=lifespan)

static_dir = Path(__file__).parent / "static"
if static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    from fastapi.responses import FileResponse

    @app.get("/")
    def index():
        return FileResponse(str(static_dir / "index.html"))


app.include_router(instances.router)
app.include_router(models.router)
app.include_router(import_gguf.router)
app.include_router(pull.router)
app.include_router(gguf_library.router)
app.include_router(credentials.router)
app.include_router(tasks.router)


def main():
    parser = argparse.ArgumentParser(description="LlamaDeck")
    parser.add_argument("--port", type=int, default=int(os.environ.get("LLAMADECK_PORT", settings.port)))
    parser.add_argument("--host", default=os.environ.get("LLAMADECK_HOST", settings.host))
    parser.add_argument("--gguf-dir", default=settings.gguf_dir)
    args = parser.parse_args()

    settings.port = args.port
    settings.host = args.host
    settings.gguf_dir = args.gguf_dir
    settings.save()

    print(f"  LlamaDeck running at http://{args.host}:{args.port}")
    uvicorn.run("backend.main:app", host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
