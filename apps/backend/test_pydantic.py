from pydantic import BaseModel
class Test(BaseModel):
    id: str
try:
    Test.model_validate({"_id": "123"})
except Exception as e:
    print(e)
