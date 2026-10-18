from contextlib import asynccontextmanager

from fastapi import FastAPI
from .interno import proteger_servicio
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .routers import dashboard, etl_manual
from .events import iniciar_consumidor
from .scheduler import iniciar_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    connection = await iniciar_consumidor()
    scheduler = iniciar_scheduler()
    yield
    scheduler.shutdown()
    await connection.close()


app = FastAPI(title="Analytics Service", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
proteger_servicio(app)
app.include_router(dashboard.router)
app.include_router(etl_manual.router)


@app.get("/")
def servir_dashboard():
    return FileResponse("app/static/dashboard.html")


@app.get("/health")
def health():
    return {"status": "ok", "service": "analytics-service"}