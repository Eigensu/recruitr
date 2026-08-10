import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db_names = await client.list_database_names()
    
    for db_name in db_names:
        db = client[db_name]
        colls = await db.list_collection_names()
        if 'candidates' in colls:
            count = await db.candidates.count_documents({})
            print(f"Database: {db_name}, Candidates count: {count}")
            if count > 0:
                pipeline = [
                    {"$group": {
                        "_id": None,
                        "avg_salary": {"$avg": "$salary"},
                        "max_salary": {"$max": "$salary"},
                        "min_salary": {"$min": "$salary"},
                        "avg_expected": {"$avg": "$expected_salary"},
                        "max_expected": {"$max": "$expected_salary"},
                        "min_expected": {"$min": "$expected_salary"},
                        "salary_count": {"$sum": {"$cond": [{"$gt": ["$salary", None]}, 1, 0]}},
                        "expected_count": {"$sum": {"$cond": [{"$gt": ["$expected_salary", None]}, 1, 0]}}
                    }}
                ]
                async for doc in db.candidates.aggregate(pipeline):
                    print(doc)
                roles = await db.candidates.distinct("current_role")
                print(f"Total distinct roles: {len(roles)}")
                print(f"Sample roles: {roles[:10]}")
                print("-" * 40)

asyncio.run(main())
