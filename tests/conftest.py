import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.app import app
from src.dependencies import get_session
from src.domain.models import Base
from contextlib import contextmanager

# --- 1) Motor de pruebas AISLADO (SQLite) ---
# Opción A: en memoria (más rápido, pero cada conexión es una DB distinta sin pool especial)
# TEST_DB_URL = "sqlite:///:memory:"

# Opción B: archivo temporal (misma BD para toda la suite)
_tmp = tempfile.NamedTemporaryFile(prefix="msvcrm_test_", suffix=".db", delete=False)
TEST_DB_URL = f"sqlite:///{_tmp.name}"

engine_test = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},  # requerido por SQLite con TestClient
    future=True,
)
SessionLocalTest = sessionmaker(bind=engine_test, autoflush=False, autocommit=False, future=True)

# Crea todas las tablas en la BD de pruebas
Base.metadata.create_all(bind=engine_test)

# --- 2) Monkeypatch de tu infraestructura para que NUNCA use la DB real ---
@pytest.fixture(scope="session", autouse=True)
def _patch_infrastructure():
    import src.infrastructure.infrastructure as infra

    original_engine = getattr(infra, "engine", None)
    original_session_for_schema = getattr(infra, "session_for_schema", None)

    @contextmanager
    def session_for_schema_test(_schema: str):
        """Ignora el schema y devuelve sesión SQLite de test como context manager."""
        db = SessionLocalTest()
        try:
            yield db
            db.commit()  # opcional; deja en no-op si prefieres solo flush
        finally:
            db.close()

    infra.engine = engine_test
    infra.session_for_schema = session_for_schema_test

    yield

    # (opcional) restaurar
    if original_engine is not None:
        infra.engine = original_engine
    if original_session_for_schema is not None:
        infra.session_for_schema = original_session_for_schema

# --- 3) Sesión por prueba + override de dependencia FastAPI ---
@pytest.fixture()
def db_session():
    db = SessionLocalTest()
    try:
        yield db
    finally:
        db.rollback()
        db.close()

@pytest.fixture(autouse=True)
def _override_get_session(db_session):
    # Asegura que TODOS los endpoints usen la sesión SQLite de pruebas
    def _get_session_override():
        return db_session
    app.dependency_overrides[get_session] = _get_session_override
    yield
    app.dependency_overrides.clear()

# --- 4) Cliente FastAPI de pruebas ---
@pytest.fixture()
def client():
    return TestClient(app)

# --- 5) Headers por defecto (si usas multi-país) ---
@pytest.fixture()
def headers():
    from src.config import settings
    return {settings.COUNTRY_HEADER: settings.DEFAULT_SCHEMA}
