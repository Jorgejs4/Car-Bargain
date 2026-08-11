import os

# Debe establecerse ANTES de importar app.* para que el engine de la app
# apunte a la BD de test (las env vars tienen prioridad sobre .env).
os.environ["DATABASE_URL"] = "postgresql+psycopg://carbargains:carbargains@localhost:5432/carbargains_test"

import app.models  # noqa: F401  # registra los modelos en Base.metadata
import pytest
from app.db.base import Base
from sqlalchemy import create_engine, text

TEST_DB_URL = os.environ["DATABASE_URL"]
TEST_DB_NAME = "carbargains_test"


@pytest.fixture(scope="session", autouse=True)
def _test_database():
    admin_url = TEST_DB_URL.rsplit("/", 1)[0] + "/carbargains"
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": TEST_DB_NAME}
        ).scalar()
        if not exists:
            conn.execute(text("CREATE DATABASE carbargains_test"))
    admin.dispose()

    engine = create_engine(TEST_DB_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def db_session():
    """Cada test corre en una transacción que se revierte al final (aislamiento)."""
    from app.db.session import engine
    from sqlalchemy.orm import Session

    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture(autouse=True)
def _clean_committed_data():
    """Borra después de cada test los datos commiteados por tasks (sesión propia).

    Los tests que ejecutan tasks Celery escriben con `SessionLocal().commit()`, que
    escapa al rollback del `db_session`; sin esta limpieza contaminan al resto.
    """
    yield
    from app.db.session import engine

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE listing_events, listing_snapshots, listings, vehicles CASCADE"))
