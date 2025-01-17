import os
from dotenv import load_dotenv

load_dotenv()

class Cfg:
    URL = os.getenv("DATABASE_URL")
    SALT = os.getenv("SALT")
    SECRET_KEY = os.getenv("SECRET_KEY")