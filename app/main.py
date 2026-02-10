from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ORIGINS
from app.db import init_db
from app.models import Property, Report  # noqa: F401 — registers models with Base
from app.routers import properties, simulation, reports


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="DEMANDER API",
    description="Demand Engine for Market Analysis, Needs, Decision-making, Estimation, and Recommendations",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(properties.router, prefix="/api/properties", tags=["Properties"])
app.include_router(simulation.router, prefix="/api/simulation", tags=["Simulation"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "demander-api", "version": "0.1.0"}
