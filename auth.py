import os
from datetime import datetime, timedelta, timezone

import bcrypt
from dotenv import load_dotenv
from jose import jwt
from fastapi.security import OAuth2PasswordBearer


# Load values from .env
load_dotenv()

# JWT configuration
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")


# Check SECRET_KEY
if not SECRET_KEY:
    raise ValueError("SECRET_KEY is missing in the .env file")


# OAuth2 configuration
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="login"
)


# --------------------------------------------------
# Password Functions
# --------------------------------------------------

def hash_password(password: str) -> str:
    """
    Hash a plain password using bcrypt.
    """

    password_bytes = password.encode("utf-8")

    hashed_password = bcrypt.hashpw(
        password_bytes,
        bcrypt.gensalt()
    )

    return hashed_password.decode("utf-8")


def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
    """
    Verify a plain password against a stored bcrypt hash.
    """

    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8")
    )


# --------------------------------------------------
# JWT Function
# --------------------------------------------------

def create_access_token(
    data: dict,
    expires_minutes: int = 30
) -> str:
    """
    Create a JWT access token.
    """

    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes
    )

    to_encode.update({
        "exp": expire
    })

    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

