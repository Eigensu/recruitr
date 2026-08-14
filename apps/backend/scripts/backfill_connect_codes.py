import asyncio
import logging
import random

from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _generate_connect_code() -> str:
    allowed_chars = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(random.choices(allowed_chars, k=8))


async def main():
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DB_NAME]

    collection = db["referee_users"]

    # Find all referees without a connect_code
    cursor = collection.find({"connect_code": {"$exists": False}})
    referees = await cursor.to_list(length=None)

    if not referees:
        logger.info("No referees without a connect code found.")
        return

    logger.info(f"Found {len(referees)} referees needing a connect code.")

    updated_count = 0
    for referee in referees:
        while True:
            code = _generate_connect_code()
            # Check if this code already exists
            existing = await collection.find_one({"connect_code": code})
            if not existing:
                try:
                    await collection.update_one(
                        {"_id": referee["_id"]}, {"$set": {"connect_code": code}}
                    )
                    updated_count += 1
                    logger.info(f"Updated referee {referee.get('email')} with code {code}")
                    break
                except Exception as e:
                    logger.error(f"Failed to update referee {referee.get('email')}: {e}")
                    # Could be DuplicateKeyError for connect_code if race condition
                    if "connect_code" in str(e).lower():
                        continue  # loop and retry
                    break  # unknown error, stop looping for this referee

    logger.info(f"Successfully backfilled {updated_count} referees.")


if __name__ == "__main__":
    asyncio.run(main())
