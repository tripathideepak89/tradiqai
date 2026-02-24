"""Supabase Configuration and Integration"""
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Supabase Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://lmpajbaylwrlqtcqmwoo.supabase.co")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

# Validate service key format (JWT should have 3 parts separated by dots)
if SUPABASE_SERVICE_KEY and len(SUPABASE_SERVICE_KEY.split('.')) != 3:
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"⚠️ SUPABASE_SERVICE_KEY appears invalid! Length: {len(SUPABASE_SERVICE_KEY)}, Parts: {len(SUPABASE_SERVICE_KEY.split('.'))}")
    logger.error(f"   Prefix: {SUPABASE_SERVICE_KEY[:30]}...")
    logger.error(f"   Suffix: ...{SUPABASE_SERVICE_KEY[-30:]}")
    logger.error("   JWT tokens should have 3 parts (header.payload.signature)")
elif SUPABASE_SERVICE_KEY:
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"✅ SUPABASE_SERVICE_KEY loaded: {len(SUPABASE_SERVICE_KEY)} chars, valid JWT format")
else:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning("⚠️ SUPABASE_SERVICE_KEY is not set!")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# Admin client for server-side operations (uses service key)
def get_supabase_admin() -> Client:
    """Get Supabase client with service role key for admin operations"""
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def get_supabase_client() -> Client:
    """Get Supabase client instance"""
    return supabase


# Database connection string for SQLAlchemy
def get_supabase_db_url() -> str:
    """
    Get Supabase PostgreSQL connection URL for SQLAlchemy
    
    Format: postgresql://postgres:[PASSWORD]@db.lmpajbaylwrlqtcqmwoo.supabase.co:5432/postgres
    """
    password = os.getenv("SUPABASE_DB_PASSWORD", "")
    project_ref = "lmpajbaylwrlqtcqmwoo"
    
    # Supabase PostgreSQL connection (pooler for better performance)
    return f"postgresql://postgres.{project_ref}:{password}@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"


# Direct connection (without pooler) - use for migrations
def get_supabase_db_url_direct() -> str:
    """Get direct Supabase PostgreSQL connection URL (for migrations)"""
    password = os.getenv("SUPABASE_DB_PASSWORD", "")
    project_ref = "lmpajbaylwrlqtcqmwoo"
    
    return f"postgresql://postgres:{password}@db.{project_ref}.supabase.co:5432/postgres"
