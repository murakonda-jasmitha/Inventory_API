from fastapi import (
    FastAPI,
    Request,
    Depends,
    HTTPException,
    status
)

from pydantic import BaseModel
import mysql.connector
import os
import re
import secrets
import hashlib
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta

from dotenv import load_dotenv
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm

from jose import JWTError, jwt

from auth import (
    hash_password,
    verify_password,
    create_access_token,
    oauth2_scheme,
    SECRET_KEY,
    ALGORITHM
)


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()


# ============================================================
# CREATE FASTAPI APP
# ============================================================

app = FastAPI(
    title="Inventory Management API",
    description="Inventory Management System with Authentication and Authorization",
    version="1.0.0"
)


# ============================================================
# STATIC FILES
# ============================================================

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)


# ============================================================
# HTML TEMPLATES
# ============================================================

templates = Jinja2Templates(
    directory="templates"
)


# ============================================================
# HOME PAGE
# ============================================================

@app.get("/")
def home(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="login.html"
    )


# ============================================================
# LOGIN PAGE
# ============================================================

@app.get("/login-page")
def login_page(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="login.html"
    )


# ============================================================
# REGISTER PAGE
# ============================================================

@app.get("/register-page")
def register_page(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="register.html"
    )


# ============================================================
# INVENTORY PAGE
# ============================================================

@app.get("/inventory")
def inventory_page(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="index.html"
    )


# ============================================================
# MYSQL CONNECTION - AIVEN
# ============================================================

conn = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT")),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME"),

    # Aiven SSL
    ssl_disabled=False,
    ssl_verify_cert=False,
    ssl_verify_identity=False
)

print("Aiven MySQL Connected Successfully")


# ============================================================
# PRODUCT MODEL
# ============================================================

class Product(BaseModel):

    name: str
    price: float
    quantity: int


# ============================================================
# REGISTRATION MODELS AND EMAIL OTP HELPERS
# ============================================================

class UserRegister(BaseModel):
    full_name: str
    username: str
    email: str
    phone: str
    password: str


class VerifyRegistrationOTP(BaseModel):
    email: str
    otp: str


def validate_password(password: str) -> None:
    if (
        len(password) < 8
        or not re.search(r"[A-Z]", password)
        or not re.search(r"[a-z]", password)
        or not re.search(r"[0-9]", password)
        or not re.search(r"[^A-Za-z0-9]", password)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Password must be at least 8 characters long and contain "
                "an uppercase letter, a lowercase letter, a number, "
                "and a special character."
            ),
        )


def send_otp_email(email: str, otp: str) -> None:
    sender = os.getenv("EMAIL_ADDRESS")
    app_password = os.getenv("EMAIL_APP_PASSWORD")
    if not sender or not app_password:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Email service is not configured. Check EMAIL_ADDRESS and EMAIL_APP_PASSWORD.",
        )

    message = EmailMessage()
    message["Subject"] = "Inventory Management - Email Verification OTP"
    message["From"] = sender
    message["To"] = email
    message.set_content(
        f"Your Inventory Management System verification code is {otp}. "
        "It expires in 5 minutes. If you did not request this, ignore this email."
    )

    try:
        # Gmail SMTP SSL. The timeout prevents the browser from waiting indefinitely.
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
            server.login(sender, app_password.replace(" ", ""))
            server.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        print("OTP email delivery failed:", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not send the verification email. Check Gmail App Password and SMTP access.",
        )


# ============================================================
# STEP 1 - SEND REGISTRATION OTP
# ============================================================

@app.post("/register/send-otp")
def send_registration_otp(user: UserRegister):
    full_name = user.full_name.strip()
    username = user.username.strip()
    email = user.email.strip().lower()
    phone = user.phone.strip()
    password = user.password

    if not full_name or not username or not phone:
        raise HTTPException(status_code=400, detail="Please fill in all required fields.")
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    if not re.fullmatch(r"[0-9+()\- ]{7,20}", phone):
        raise HTTPException(status_code=400, detail="Enter a valid phone number.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,50}", username):
        raise HTTPException(status_code=400, detail="Username must be 3-50 characters using letters, numbers, dots, underscores, or hyphens.")
    validate_password(password)

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT id FROM users WHERE username = %s OR email = %s",
            (username, email),
        )
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Username or email is already registered.")

        # Replace any existing pending attempt for this username or email.
        cursor.execute(
            "DELETE FROM pending_registrations WHERE username = %s OR email = %s",
            (username, email),
        )

        otp = f"{secrets.randbelow(1_000_000):06d}"
        otp_hash = hashlib.sha256(otp.encode("utf-8")).hexdigest()
        password_hash = hash_password(password)
        expires_at = datetime.utcnow() + timedelta(minutes=5)

        cursor.execute(
            """INSERT INTO pending_registrations
               (full_name, username, email, phone, password_hash, otp_hash, expires_at, attempts)
               VALUES (%s, %s, %s, %s, %s, %s, %s, 0)""",
            (full_name, username, email, phone, password_hash, otp_hash, expires_at),
        )
        conn.commit()

        try:
            send_otp_email(email, otp)
        except HTTPException:
            cursor.execute("DELETE FROM pending_registrations WHERE email = %s", (email,))
            conn.commit()
            raise

        return {"message": "OTP sent to your email. It expires in 5 minutes.", "email": email}
    except mysql.connector.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=400, detail="Username or email is already pending registration.")
    finally:
        cursor.close()


# ============================================================
# STEP 2 - VERIFY OTP AND CREATE ACCOUNT
# ============================================================

@app.post("/register/verify-otp")
def verify_registration_otp(data: VerifyRegistrationOTP):
    email = data.email.strip().lower()
    otp = data.otp.strip()
    if not re.fullmatch(r"[0-9]{6}", otp):
        raise HTTPException(status_code=400, detail="Enter the six-digit OTP.")

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT * FROM pending_registrations WHERE email = %s",
            (email,),
        )
        pending = cursor.fetchone()
        if not pending:
            raise HTTPException(status_code=400, detail="No pending registration found. Request a new OTP.")

        expires_at = pending["expires_at"]
        # MySQL drivers may return a naive datetime; compare as naive UTC consistently.
        if expires_at <= datetime.utcnow():
            cursor.execute("DELETE FROM pending_registrations WHERE email = %s", (email,))
            conn.commit()
            raise HTTPException(status_code=400, detail="OTP expired. Please register again to request a new OTP.")

        if pending["attempts"] >= 5:
            cursor.execute("DELETE FROM pending_registrations WHERE email = %s", (email,))
            conn.commit()
            raise HTTPException(status_code=400, detail="Too many incorrect attempts. Please register again.")

        supplied_hash = hashlib.sha256(otp.encode("utf-8")).hexdigest()
        if not secrets.compare_digest(supplied_hash, pending["otp_hash"]):
            cursor.execute(
                "UPDATE pending_registrations SET attempts = attempts + 1 WHERE email = %s",
                (email,),
            )
            conn.commit()
            raise HTTPException(status_code=400, detail="Incorrect OTP. Please try again.")

        cursor.execute(
            """INSERT INTO users (username, password_hash, role, full_name, email, phone)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (
                pending["username"], pending["password_hash"], "user",
                pending["full_name"], pending["email"], pending["phone"],
            ),
        )
        new_id = cursor.lastrowid
        cursor.execute("DELETE FROM pending_registrations WHERE email = %s", (email,))
        conn.commit()
        return {
            "message": "Email verified and account created successfully. You can now log in.",
            "user_id": new_id,
            "username": pending["username"],
            "role": "user",
        }
    except mysql.connector.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=400, detail="Username or email is already registered.")
    finally:
        cursor.close()


# ============================================================
# LOGIN
# ============================================================

@app.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends()
):

    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT
            id,
            username,
            password_hash,
            role
        FROM users
        WHERE username = %s
    """

    print("Username:", form_data.username)

    cursor.execute(
        query,
        (form_data.username,)
    )

    user = cursor.fetchone()

    cursor.close()

    # User does not exist
    if not user:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )

    # Verify password
    if not verify_password(
        form_data.password,
        user["password_hash"]
    ):

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )

    # Create JWT token
    access_token = create_access_token(
        {
            "username": user["username"],
            "role": user["role"]
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user["username"],
        "role": user["role"]
    }


# ============================================================
# GET CURRENT USER
# ============================================================

def get_current_user(
    token: str = Depends(oauth2_scheme)
):

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={
            "WWW-Authenticate": "Bearer"
        }
    )

    try:

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        username = payload.get("username")
        role = payload.get("role")

        if username is None or role is None:

            raise credentials_exception

        return {
            "username": username,
            "role": role
        }

    except JWTError:

        raise credentials_exception


# ============================================================
# CURRENT USER API
# ============================================================

@app.get("/me")
def get_me(
    current_user: dict = Depends(
        get_current_user
    )
):

    return {
        "username": current_user["username"],
        "role": current_user["role"]
    }


# ============================================================
# ADMIN AUTHORIZATION
# ============================================================

def require_admin(
    current_user: dict = Depends(
        get_current_user
    )
):

    if current_user["role"] != "admin":

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    return current_user


# ============================================================
# GET - ALL PRODUCTS
# LOGIN REQUIRED
# ============================================================

@app.get("/products")
def get_products(
    current_user: dict = Depends(
        get_current_user
    )
):

    cursor = conn.cursor(
        dictionary=True
    )

    cursor.execute(
        "SELECT * FROM products"
    )

    products = cursor.fetchall()

    cursor.close()

    return products


# ============================================================
# GET - PRODUCT BY ID
# LOGIN REQUIRED
# ============================================================

@app.get("/products/{product_id}")
def get_product(
    product_id: int,
    current_user: dict = Depends(
        get_current_user
    )
):

    cursor = conn.cursor(
        dictionary=True
    )

    query = """
        SELECT *
        FROM products
        WHERE product_id = %s
    """

    cursor.execute(
        query,
        (product_id,)
    )

    product = cursor.fetchone()

    cursor.close()

    if product:

        return product

    return {
        "message": "Product not found"
    }


# ============================================================
# POST - CREATE PRODUCT
# ADMIN ONLY
# ============================================================

@app.post("/products")
def create_product(
    product: Product,
    current_user: dict = Depends(
        require_admin
    )
):

    cursor = conn.cursor()

    query = """
        INSERT INTO products
        (product_name, sell_price, quantity)
        VALUES (%s, %s, %s)
    """

    values = (
        product.name,
        product.price,
        product.quantity
    )

    cursor.execute(
        query,
        values
    )

    conn.commit()

    new_id = cursor.lastrowid

    cursor.close()

    return {
        "message": "Product created successfully",
        "product_id": new_id
    }


# ============================================================
# PUT - UPDATE PRODUCT
# ADMIN ONLY
# ============================================================

@app.put("/products/{product_id}")
def update_product(
    product_id: int,
    product: Product,
    current_user: dict = Depends(
        require_admin
    )
):

    cursor = conn.cursor()

    query = """
        UPDATE products
        SET product_name = %s,
            sell_price = %s,
            quantity = %s
        WHERE product_id = %s
    """

    values = (
        product.name,
        product.price,
        product.quantity,
        product_id
    )

    cursor.execute(
        query,
        values
    )

    conn.commit()

    if cursor.rowcount == 0:

        cursor.close()

        return {
            "message": "Product not found"
        }

    cursor.close()

    return {
        "message": "Product updated successfully",
        "product_id": product_id
    }


# ============================================================
# DELETE - DELETE PRODUCT
# ADMIN ONLY
# ============================================================

@app.delete("/products/{product_id}")
def delete_product(
    product_id: int,
    current_user: dict = Depends(
        require_admin
    )
):

    cursor = conn.cursor()

    query = """
        DELETE FROM products
        WHERE product_id = %s
    """

    cursor.execute(
        query,
        (product_id,)
    )

    conn.commit()

    if cursor.rowcount == 0:

        cursor.close()

        return {
            "message": "Product not found"
        }

    cursor.close()

    return {
        "message": "Product deleted successfully",
        "product_id": product_id
    }