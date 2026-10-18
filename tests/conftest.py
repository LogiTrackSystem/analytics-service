"""Pruebas de Analytics con SQLite en memoria (sin PostgreSQL, RabbitMQ ni los otros servicios)."""
import os
import sys

os.environ["DATABASE_URL"] = "sqlite://"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app import models  # noqa: F401
from app.routers import dashboard


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sesion = sessionmaker(bind=engine, autoflush=False)()
    yield sesion
    sesion.close()
    engine.dispose()


@pytest.fixture()
def api(db):
    # Solo el router del dashboard: no se levanta RabbitMQ ni el scheduler.
    app = FastAPI()
    app.include_router(dashboard.router)

    def _get_db():
        yield db
    app.dependency_overrides[get_db] = _get_db
    return TestClient(app)
