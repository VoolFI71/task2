from jose import JWTError, jwt
from fastapi import HTTPException
from config.settings import Cfg

ALGORITHM = "HS256"

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, Cfg.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token decoding error: {str(e)}")