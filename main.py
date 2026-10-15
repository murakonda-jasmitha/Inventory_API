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
# USER REGISTRATION MODEL
# ============================================================

class UserRegister(BaseModel):

    username: str
    password: str


# ============================================================
# REGISTER USER
# ============================================================

@app.post("/register")
def register_user(user: UserRegister):

    cursor = conn.cursor(dictionary=True)

    # Check whether username already exists
    cursor.execute(
        """
        SELECT id, username
        FROM users
        WHERE username = %s
        """,
        (user.username,)
    )

    existing_user = cursor.fetchone()

    if existing_user:

        cursor.close()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )

    # Hash password
    hashed_password = hash_password(
        user.password
    )

    # New users are ALWAYS normal users
    query = """
        INSERT INTO users
        (username, password_hash, role)
        VALUES (%s, %s, %s)
    """

    values = (
        user.username,
        hashed_password,
        "user"
    )

    cursor.execute(
        query,
        values
    )

    conn.commit()

    new_id = cursor.lastrowid

    cursor.close()

    return {
        "message": "User registered successfully",
        "user_id": new_id,
        "username": user.username,
        "role": "user"
    }


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