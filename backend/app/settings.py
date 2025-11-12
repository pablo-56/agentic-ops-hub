# backend/app/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Postgres etc... (you already have these)
    PG_HOST: str = "postgres"
    PG_USER: str = "ops"
    PG_PASSWORD: str = "ops_password"
    PG_DB: str = "ops_hub"
    @property
    def pg_dsn(self) -> str:
        return f"postgresql+psycopg2://{self.PG_USER}:{self.PG_PASSWORD}@{self.PG_HOST}:5432/{self.PG_DB}"

    # Neo4j (already in your project)
    NEO4J_URI: str = "bolt://neo4j:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "neo4j_password"

    # Kafka
    KAFKA_BOOTSTRAP: str = "kafka:9092"

    # Events cache size & default window
    EVENTS_CACHE_MAX: int = 5000
    DEFAULT_WINDOW: str = "15m"

settings = Settings()
