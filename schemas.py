from pydantic import BaseModel
from datetime import datetime


class TransactionCreate(BaseModel):
    date: datetime | None = None
    from_user: str
    to_user: str
    amount: float
