import random
import jwt
from datetime import datetime, timedelta, timezone
from app.config import get_settings

def generate_math_captcha() -> tuple[str, str]:
    ops = [
        ("+", lambda a, b: a + b),
        ("-", lambda a, b: a - b),
        ("*", lambda a, b: a * b),
    ]
    op_symbol, op_func = random.choice(ops)
    
    if op_symbol == "*":
        a, b = random.randint(1, 10), random.randint(1, 10)
    else:
        a, b = random.randint(1, 50), random.randint(1, 20)
        if op_symbol == "-" and a < b:
            a, b = b, a
            
    question = f"{a} {op_symbol} {b}"
    answer = str(op_func(a, b))
    
    settings = get_settings()
    
    payload = {
        "ans": answer,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5)
    }
    
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    
    return question, token

def verify_captcha(token: str, answer: str) -> bool:
    if not token or not answer:
        return False
        
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload.get("ans") == str(answer).strip()
    except Exception:
        return False
