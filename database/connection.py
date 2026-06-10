# vpn_bot_project/database/connection.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from config import DATABASE_URL

# Create async engine for MySQL using aiomysql
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL query debugging in development
    pool_pre_ping=True
)

# Setup the async session factory
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)