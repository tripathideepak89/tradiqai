"""Test Railway database connection"""
from database import get_engine, get_redis_client
from sqlalchemy import text

print("Testing Railway PostgreSQL connection...")
engine = get_engine()
with engine.connect() as conn:
    result = conn.execute(text('SELECT version()'))
    version = result.fetchone()[0]
    print(f"✅ Connected to Railway PostgreSQL")
    print(f"   Version: {version[:80]}")

print("\nTesting Railway Redis connection...")
redis = get_redis_client()
redis.ping()
print("✅ Connected to Railway Redis successfully")

print("\n🎉 All Railway database connections working!")
