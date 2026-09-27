import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.config import settings


async def test_connection():
    engine = create_async_engine(settings.database_url)

    try:
        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT 1"))
            print("Database connection successful!")
            print("Result:", result.scalar())

    except Exception as e:
        print("Database connection failed!")
        print("Error:", e)

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(test_connection())