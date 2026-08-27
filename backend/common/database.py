"""
Database connection and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from contextlib import contextmanager
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.config import settings

# Create declarative base
Base = declarative_base()

# Database engines
hospital_engine = create_engine(
    settings.hospital_db_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=False  # Set to True for SQL query logging
)

shared_engine = create_engine(
    settings.shared_db_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=False
)

# Session factories
HospitalSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=hospital_engine
)

SharedSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=shared_engine
)


# Dependency for hospital database
def get_hospital_db() -> Session:
    """
    Dependency function to get hospital database session
    Usage: db: Session = Depends(get_hospital_db)
    """
    db = HospitalSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Dependency for shared database
def get_shared_db() -> Session:
    """
    Dependency function to get shared database session
    Usage: db: Session = Depends(get_shared_db)
    """
    db = SharedSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Context manager for hospital database
@contextmanager
def hospital_db_session():
    """
    Context manager for hospital database sessions
    Usage: with hospital_db_session() as db:
    """
    db = HospitalSessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# Context manager for shared database
@contextmanager
def shared_db_session():
    """
    Context manager for shared database sessions
    Usage: with shared_db_session() as db:
    """
    db = SharedSessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# Database connection test functions
def test_hospital_connection():
    """Test hospital database connection"""
    try:
        with hospital_db_session() as db:
            db.execute("SELECT 1")
        return True
    except Exception as e:
        print(f"Hospital DB connection failed: {e}")
        return False


def test_shared_connection():
    """Test shared database connection"""
    try:
        with shared_db_session() as db:
            db.execute("SELECT 1")
        return True
    except Exception as e:
        print(f"Shared DB connection failed: {e}")
        return False


# Initialize database (create tables if they don't exist)
def init_db():
    """Initialize database - create tables"""
    # Import models here to avoid circular imports
    from common.models import Base as ModelsBase
    
    # Create all tables in hospital database
    ModelsBase.metadata.create_all(bind=hospital_engine)
    print("Hospital database tables created/verified")
    
    # Note: Shared DB tables are managed separately via migrations
    print("Database initialization complete")


if __name__ == "__main__":
    print("Testing database connections...")
    print(f"Hospital DB: {'OK' if test_hospital_connection() else 'FAILED'}")
    print(f"Shared DB: {'OK' if test_shared_connection() else 'FAILED'}")
