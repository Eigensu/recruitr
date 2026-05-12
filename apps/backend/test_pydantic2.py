from pydantic import BaseModel, Field, ConfigDict
from bson import ObjectId

class BaseAnalyticsItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field(alias="_id")

try:
    print(BaseAnalyticsItem.model_validate({"_id": ObjectId()}).model_dump())
except Exception as e:
    print(e)
