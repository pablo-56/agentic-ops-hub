# backend/app/db.py
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
import time, sys
from .config import settings

engine = create_engine(settings.pg_dsn, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

def init_db():
    # Robust retry so we don't crash if Postgres isn't ready yet
    for attempt in range(1, 31):
        try:
            _init_db_once()
            print(f"[init_db] Database ready on attempt {attempt}")
            return
        except OperationalError as e:
            print(f"[init_db] Postgres not ready (attempt {attempt}/30): {e}")
            time.sleep(2)
    print("[init_db] Postgres failed to become ready after retries", file=sys.stderr)
    raise

def _init_db_once():
    with engine.begin() as conn:
        # pgvector (already used for docs/embeddings)
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))

        # --- Incidents --------------------------------------------------------
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS incidents (
            id SERIAL PRIMARY KEY,
            incident_id VARCHAR(64) UNIQUE,
            summary TEXT NOT NULL,
            severity VARCHAR(16) NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'investigating',
            resolution_summary TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );"""))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS incident_entities (
            id SERIAL PRIMARY KEY,
            incident_id VARCHAR(64) NOT NULL,
            entity_type VARCHAR(64) NOT NULL,
            entity_id VARCHAR(128) NOT NULL,
            role VARCHAR(64) DEFAULT 'affected',
            created_at TIMESTAMPTZ DEFAULT NOW()
        );"""))
        # Needed so ON CONFLICT (incident_id, entity_type, entity_id, role) works
        conn.execute(text("""
        DO $$
        BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'uq_incident_entities_tuple'
              AND conrelid = 'public.incident_entities'::regclass
        ) THEN
            ALTER TABLE public.incident_entities
            ADD CONSTRAINT uq_incident_entities_tuple
            UNIQUE (incident_id, entity_type, entity_id, role);
        END IF;
        END$$;"""))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_incident_entities_incident_id ON incident_entities (incident_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_incident_entities_entity ON incident_entities (entity_type, entity_id);"))

        # --- Tickets ----------------------------------------------------------
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS tickets (
            id SERIAL PRIMARY KEY,
            ticket_id VARCHAR(64) UNIQUE,
            system VARCHAR(64),
            external_id VARCHAR(128),
            status VARCHAR(32),
            incident_id VARCHAR(64),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );"""))
        conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();"))
        conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();"))

        # --- Runbooks & Bindings ---------------------------------------------
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS runbooks (
            id SERIAL PRIMARY KEY,
            runbook_id VARCHAR(64) UNIQUE,
            name TEXT,
            description TEXT,
            risk_level VARCHAR(16),
            enabled BOOLEAN DEFAULT TRUE
        );"""))

        # Bind a runbook to graph entities (by type + a simple LIKE pattern on id)
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS runbook_bindings (
            id SERIAL PRIMARY KEY,
            runbook_id VARCHAR(64) NOT NULL,
            entity_type VARCHAR(64) NOT NULL,
            match_pattern TEXT NOT NULL
        );"""))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_runbook_bindings_lookup ON runbook_bindings (entity_type, runbook_id);"))

        # --- Agent actions (audit log) ---------------------------------------
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS agent_actions (
            id SERIAL PRIMARY KEY,
            action_id VARCHAR(64) UNIQUE,
            runbook_id VARCHAR(64),
            action_type VARCHAR(64),
            incident_id VARCHAR(64),
            entity_id VARCHAR(128),
            status VARCHAR(32),
            triggered_by VARCHAR(64),
            approved_by VARCHAR(64),
            reasoning TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );"""))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_agent_actions_incident ON agent_actions (incident_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_agent_actions_entity ON agent_actions (entity_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_agent_actions_status ON agent_actions (status);"))

        # --- Documents (unchanged) -------------------------------------------
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS documents (
            id SERIAL PRIMARY KEY,
            doc_id VARCHAR(64) UNIQUE,
            title TEXT,
            content TEXT,
            metadata JSONB,
            embedding VECTOR(768)
        );"""))
