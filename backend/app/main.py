from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import alarmes, analyse, consultation, dashboard, fournees, fours, parametrage

app = FastAPI(title="PortailTTH API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8100"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fours.router, prefix="/api")
app.include_router(fournees.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(analyse.router, prefix="/api")
app.include_router(alarmes.router, prefix="/api")
app.include_router(parametrage.router, prefix="/api")
app.include_router(consultation.router, prefix="/api")
