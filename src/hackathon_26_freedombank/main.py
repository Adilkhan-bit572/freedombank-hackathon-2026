from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import CORS_ORIGINS
from .db import init_db
from .routers import appeals, checklist, conversations, evaluations


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # create tables on startup
    yield


app = FastAPI(title="FreedomBank Hackathon API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Validation-Problems", "X-Non-Standard"],  # read by the results.json button
)
app.include_router(conversations.router)
app.include_router(evaluations.router)
app.include_router(checklist.router)
app.include_router(appeals.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
