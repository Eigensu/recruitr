import asyncio

from app.database import init_db
from app.modules.dashboard.repository import fetch_clients, fetch_mappings
from app.modules.dashboard.schemas import (
    ClientAnalyticsItem,
    DashboardFilters,
    MappingAnalyticsItem,
)


async def main():
    await init_db()
    filters = DashboardFilters()
    res = await fetch_clients(filters, 1, 10)
    for item in res["items"]:
        ClientAnalyticsItem.model_validate(item)
    print("clients ok")
    res = await fetch_mappings(filters, 1, 10)
    for item in res["items"]:
        MappingAnalyticsItem.model_validate(item)
    print("mappings ok")


if __name__ == "__main__":
    asyncio.run(main())
