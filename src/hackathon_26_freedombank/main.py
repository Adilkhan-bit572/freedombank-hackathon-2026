from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db import init_db
from .routers import items


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # create tables on startup
    yield


app = FastAPI(title="FreedomBank Hackathon API", lifespan=lifespan)
app.include_router(items.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
