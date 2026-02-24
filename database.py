"""Database connection and session management"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings
import redis
import logging

logger = logging.getLogger(__name__)

# Lazy initialization to prevent import-time crashes
_engine = None
_SessionLocal = None
_redis_client = None

Base = declarative_base()


def get_engine():
    """Lazy initialize database engine"""
    global _engine, _SessionLocal
    if _engine is None:
        try:
            logger.info(f"Initializing database engine...")
            
            # Convert postgresql:// to postgresql+psycopg:// for psycopg3
            database_url = settings.database_url
            if database_url.startswith("postgresql://"):
                database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
            
            _engine = create_engine(
                database_url,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20
            )
            _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
            logger.info("Database engine initialized successfully")
        except Exception as e:
            logger.error(f"Database engine initialization failed: {e}")
            raise
    return _engine


def get_session_local():
    """Get SessionLocal (lazy initialized)"""
    if _SessionLocal is None:
        get_engine()  # Initialize if not already done
    return _SessionLocal


def get_redis_client():
    """Lazy initialize Redis client"""
    global _redis_client
    if _redis_client is None:
        try:
            logger.info(f"Initializing Redis client...")
            _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
            logger.info("Redis client initialized successfully")
        except Exception as e:
            logger.error(f"Redis initialization failed: {e}")
            # Don't crash - Redis is optional for some features
            _redis_client = None
    return _redis_client


# For backwards compatibility - but code should use get_engine(), etc.
engine = None  # Will be set by get_engine()
SessionLocal = None  # Will be set by get_session_local()
redis_client = None  # Will be set by get_redis_client()


def get_db():
    """Get database session"""
    session_factory = get_session_local()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables"""
    # Import models so they're registered with Base.metadata
    import models  # noqa: F401
    
    eng = get_engine()
    Base.metadata.create_all(bind=eng)
