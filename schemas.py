from pydantic import BaseModel
from datetime import datetime


class TransactionCreate(BaseModel):
    from_user: str
    to_user: str
    amount: float
    date: datetime
