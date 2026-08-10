import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath('apps/backend'))

from pymongo import AsyncMongoClient
from app.config import settings

async def main():
    client = AsyncMongoClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DB_NAME]
    
    colls = await db.list_collection_names()
    if 'candidates' in colls:
        count = await db.candidates.count_documents({})
        print(f"Database: {settings.MONGODB_DB_NAME}, Candidates count: {count}")
        if count > 0:
            pipeline = [
                {
                    "$addFields": {
                        "num_salary": {"$convert": {"input": "$salary", "to": "double", "onError": None, "onNull": None}},
                        "num_expected": {"$convert": {"input": "$expected_salary", "to": "double", "onError": None, "onNull": None}}
                    }
                },
                {"$group": {
                    "_id": None,
                    "avg_salary": {"$avg": "$num_salary"},
                    "max_salary": {"$max": "$num_salary"},
                    "min_salary": {"$min": "$num_salary"},
                    "avg_expected": {"$avg": "$num_expected"},
                    "max_expected": {"$max": "$num_expected"},
                    "min_expected": {"$min": "$num_expected"},
                    "salary_count": {"$sum": {"$cond": [{"$ne": ["$num_salary", None]}, 1, 0]}},
                    "expected_count": {"$sum": {"$cond": [{"$ne": ["$num_expected", None]}, 1, 0]}}
                }}
            ]
            async for doc in db.candidates.aggregate(pipeline):
                print(doc)
            roles = await db.candidates.distinct("current_role")
            print(f"Total distinct roles: {len(roles)}")
            print(f"Sample roles: {roles[:10]}")
            print("-" * 40)

asyncio.run(main())
