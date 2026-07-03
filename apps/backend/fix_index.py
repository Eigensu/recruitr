import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

async def main():
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DB_NAME]
    try:
        await db.users.drop_index("google_id_1")
        print("Dropped google_id_1 index")
    except Exception as e:
        print("Failed to drop index:", e)
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(main())
