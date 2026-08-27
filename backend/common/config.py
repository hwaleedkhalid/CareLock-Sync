"""
Configuration module for CareLock Sync
"""
from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    APP_NAME: str = "CareLock-Sync"
    APP_ENV: str = "development"
    DEBUG: bool = True
    
    # Hospital Database
    HOSPITAL_DB_HOST: str
    HOSPITAL_DB_PORT: int = 5432
    HOSPITAL_DB_NAME: str
    HOSPITAL_DB_USER: str
    HOSPITAL_DB_PASSWORD: str
    
    # Shared Database
    SHARED_DB_HOST: str
    SHARED_DB_PORT: int = 5433
    SHARED_DB_NAME: str
    SHARED_DB_USER: str
    SHARED_DB_PASSWORD: str
    SHARED_DB_SSLMODE: str = "prefer"
    
    # Security
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # AI/RAG
    OPENAI_API_KEY: Optional[str] = None
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    LLM_MODEL: str = "gpt-4"
    
    # Ollama (Sprint 4 RAG — local LLM, no API key required)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "phi3"
    MAPPING_MODEL: str = "llama3.2:3b"
    CHAT_MODEL: str = "phi3"
    CHROMA_PATH: str = "./databases/chroma"

    # Vector Database
    CHROMA_DB_PATH: str = "./databases/chroma"
    
    # Logging
    LOG_LEVEL: str = "INFO"

    # Sync Scheduler
    SYNC_ENABLED: bool = False
    SYNC_INTERVAL_SECONDS: int = 300

    # Multi-Database Adapter URLs (for CDC data source integration)
    MYSQL_URL: Optional[str] = None
    ORACLE_URL: Optional[str] = None
    SQLSERVER_URL: Optional[str] = None
    MONGODB_URL: Optional[str] = None

    @property
    def hospital_db_url(self) -> str:
        """Generate PostgreSQL connection URL for hospital database"""
        return f"postgresql://{self.HOSPITAL_DB_USER}:{self.HOSPITAL_DB_PASSWORD}@{self.HOSPITAL_DB_HOST}:{self.HOSPITAL_DB_PORT}/{self.HOSPITAL_DB_NAME}"
    
    @property
    def shared_db_url(self) -> str:
        """Generate PostgreSQL connection URL for shared database"""
        return (f"postgresql://{self.SHARED_DB_USER}:{self.SHARED_DB_PASSWORD}"
                f"@{self.SHARED_DB_HOST}:{self.SHARED_DB_PORT}/{self.SHARED_DB_NAME}"
                f"?sslmode={self.SHARED_DB_SSLMODE}")
    
    class Config:
        # Look for .env file in the config directory
        env_file = os.path.join(os.path.dirname(__file__), "..", "..", "config", ".env")
        case_sensitive = True


# Create global settings instance
settings = Settings()


# For testing/debugging
if __name__ == "__main__":
    print("=== CareLock Sync Configuration ===")
    print(f"App Name: {settings.APP_NAME}")
    print(f"Environment: {settings.APP_ENV}")
    print(f"Hospital DB URL: {settings.hospital_db_url}")
    print(f"Shared DB URL: {settings.shared_db_url}")
    print(f"Debug Mode: {settings.DEBUG}")
