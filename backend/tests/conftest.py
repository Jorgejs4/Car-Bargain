import os

# Debe establecerse ANTES de importar app.* para que el engine de la app
# apunte a la BD de test (las env vars tienen prioridad sobre .env).
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://carbargains:carbargains@localhost:5432/carbargains_test",
    ),
)

import app.models  # noqa: F401  # registra los modelos en Base.metadata
import pytest
from app.db.base import Base
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

TEST_DB_URL = os.environ["DATABASE_URL"]
TEST_DB_NAME = make_url(TEST_DB_URL).database or "carbargains_test"


def _drop_migration_only_tables(engine):
    """Elimina tablas creadas por migraciones que no tienen modelo ORM."""
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS deal_scores, price_predictions CASCADE"))


@pytest.fixture(scope="session", autouse=True)
def _test_database():
    # El servicio de CI solo garantiza la base estándar `postgres`; no asumir
    # que exista una base de desarrollo con otro nombre.
    admin_url = make_url(TEST_DB_URL).set(database="postgres")
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": TEST_DB_NAME}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    admin.dispose()

    engine = create_engine(TEST_DB_URL)
    _drop_migration_only_tables(engine)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    _drop_migration_only_tables(engine)
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


@pytest.fixture()
def committed_session():
    """Sesión con commits reales, visible para el TestClient de la API.

    `db_session` usa savepoints (el commit no persiste para otras conexiones);
    la limpieza la hace el autouse `_clean_committed_data`.
    """
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _clean_committed_data():
    """Borra después de cada test los datos commiteados por tasks (sesión propia).

    Los tests que ejecutan tasks Celery escriben con `SessionLocal().commit()`, que
    escapa al rollback del `db_session`; sin esta limpieza contaminan al resto.
    """
    yield
    from app.db.session import engine

    with engine.begin() as conn:
        conn.execute(
            text("TRUNCATE photo_analyses, listing_events, listing_snapshots, listings, vehicles CASCADE")
        )
