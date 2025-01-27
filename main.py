from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import create_engine
from config.settings import Cfg
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from schemas import TransactionCreate
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
import auth 
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)

app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

DATABASE_URL = Cfg.URL
engine= create_async_engine(DATABASE_URL, echo=False)
SessionLocal =  async_sessionmaker(autocommit=False, autoflush=False, bind=engine)

async def get_db() -> AsyncSession:
    async with SessionLocal()  as session:
        yield session

@app.post("/transaction/")
async def create_transaction(transaction: TransactionCreate, db: AsyncSession = Depends(get_db), token=Depends(oauth2_scheme)):
    logging.info("Получен запрос на создание транзакции от пользователя: %s", transaction.from_user)

    payload = auth.decode_access_token(token)
    username = payload.get("sub")
    if username is None or username!=transaction.from_user:
        logging.warning("Недействительный токен или имя пользователя не совпадает.")

        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(
        text("SELECT * FROM users WHERE username = :username"),
        {"username": transaction.from_user}
    )
    from_user = result.fetchone()

    result = await db.execute(
        text("SELECT * FROM users WHERE username = :username"),
        {"username": transaction.to_user}
    )
    to_user = result.fetchone()

    if to_user is None:
        logging.warning("Получатель не найден: %s", transaction.to_user)

        raise HTTPException(status_code=404, detail="Получатель не найден")


    if from_user.balance < transaction.amount:
        logging.warning("Недостаточно средств для пользователя: %s", transaction.from_user)
        raise HTTPException(status_code=400, detail="Недостаточно средств")

    new_from_balance = from_user.balance - transaction.amount
    new_to_balance = to_user.balance + transaction.amount

    await db.execute(
        text("UPDATE users SET balance = :balance WHERE username = :username"),
        {"balance": new_from_balance, "username": transaction.from_user}
    )
    await db.execute(
        text("UPDATE users SET balance = :balance WHERE username = :username"),
        {"balance": new_to_balance, "username": transaction.to_user}
    )

    from_user=transaction.from_user
    to_user=transaction.to_user
    amount=transaction.amount
    date=datetime.now()

    await db.execute(
        text("INSERT INTO transactions (from_user, to_user, amount, date) VALUES (:from_user, :to_user, :amount, :date)"),
        {
            "from_user": from_user,
            "to_user": to_user,
            "amount": amount,
            "date": date
        }
    )


    await db.commit() 

    logging.info("Транзакция успешна: %s -> %s, сумма: %s", transaction.from_user, transaction.to_user, transaction.amount)

    return {"message": "Транзакция успешна", "fromas_user_balance": new_from_balance, "to_user_balance": new_to_balance}

@app.post("/add/{user}")
async def create_transaction(user: str, db: AsyncSession = Depends(get_db)):
    logging.info("Получен запрос на список для токена.")

    result = await db.execute(
        text("SELECT * FROM users WHERE username = :username"),
        {"username": user}
    )
    to_user = result.fetchone()

    if to_user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    new_balance = to_user.balance + 50

    await db.execute(
        text("UPDATE users SET balance = :balance WHERE username = :username"),
        {"balance": new_balance, "username": user}
    )
    await db.commit() 

    return {"message": "Транзакция успешна", "new_balance": new_balance}

@app.get("/list/")
async def check_trans(
    limit: int = 10,
    token: str = Depends(oauth2_scheme),
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    payload = auth.decode_access_token(token)
    username = payload.get("sub")

    if username is None:
        logging.warning("Недействительный токен при попытке получить список транзакций.")
        raise HTTPException(status_code=401, detail="Invalid token")

    # выбираем limit*2 последних транзакций
    base_query = text(f"""
        SELECT *
        FROM transactions
        WHERE from_user = :username OR to_user = :username
        ORDER BY date DESC
        LIMIT {limit*2}
    """)

    all_transactions = await db.execute(base_query, {"username": username}).fetchall()

    # Применяем фильтрацию по статусу
    filtered_transactions = []
    if status == "receiving":
        filtered_transactions = [t for t in all_transactions if t.to_user == username]
    elif status == "sending":
        filtered_transactions = [t for t in all_transactions if t.from_user == username]
    else:
        filtered_transactions = all_transactions

    sorted_transactions = sorted(filtered_transactions, key=lambda x: x.date, reverse=True)

    final_transactions = sorted_transactions[:limit]

    transaction_list = [
        {"from_user": t.from_user, "to_user": t.to_user, "amount": t.amount, "date": t.date}
        for t in final_transactions
    ]

    if status == "receiving":
        status_text = "Полученные платежи"
    elif status == "sending":
        status_text = "Отправленные платежи"
    else:
        status_text = "Все платежи"

    logging.info("Возвращаем список транзакций для пользователя: %s, статус: %s, количество: %d", username, status_text, len(transaction_list))

    return {
        "Статус платежа": status_text,
        "transactions": transaction_list,
        "limit": limit,
    }