"""
Database migration script to create all tables for the House Finance Tracker
"""

import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from db_models import Base
from dotenv import load_dotenv

load_dotenv()

async def create_tables():
    """Create all database tables"""
    database_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./house_finance_tracker.db")
    
    engine = create_async_engine(database_url, echo=True)
    
    async with engine.begin() as conn:
        # Drop all tables first (be careful in production!)
        await conn.run_sync(Base.metadata.drop_all)
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
    
    await engine.dispose()
    print("All tables created successfully!")

if __name__ == "__main__":
    asyncio.run(create_tables())
