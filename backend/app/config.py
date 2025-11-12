import os
from pydantic import BaseModel

class Settings(BaseModel):
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "ops")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "ops_password")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "ops_hub")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "postgres")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))

    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "neo4j_password")

    KAFKA_BROKER: str = os.getenv("KAFKA_BROKER", "kafka:9092")

    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minio_admin")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minio_password")
    MINIO_BUCKET: str = os.getenv("MINIO_BUCKET", "ops-hub-docs")

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    API_CORS_ORIGINS: str = os.getenv("API_CORS_ORIGINS", "http://localhost:5173")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def pg_dsn(self) -> str:
        return f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

settings = Settings()
