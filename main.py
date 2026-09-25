from fastapi import FastAPI, Request
from pydantic import BaseModel
import mysql.connector
import os
from dotenv import load_dotenv
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles


# Load environment variables
load_dotenv()


# Create FastAPI app
app = FastAPI()


# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")


# HTML templates
templates = Jinja2Templates(directory="templates")


# Home page
@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html"
    )


# MySQL Connection - Aiven
conn = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT")),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME"),

    # Aiven requires SSL
    ssl_disabled=False,
    ssl_verify_cert=False,
    ssl_verify_identity=False
)

print("Aiven MySQL Connected Successfully")


# Product Model
class Product(BaseModel):
    name: str
    price: float
    quantity: int


# GET - All Products
@app.get("/products")
def get_products():

    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM products")

    products = cursor.fetchall()

    cursor.close()

    return products


# GET - Product by ID
@app.get("/products/{product_id}")
def get_product(product_id: int):

    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT *
        FROM products
        WHERE product_id = %s
    """

    cursor.execute(query, (product_id,))

    product = cursor.fetchone()

    cursor.close()

    if product:
        return product

    return {
        "message": "Product not found"
    }


# POST - Create Product
@app.post("/products")
def create_product(product: Product):

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

    cursor.execute(query, values)

    conn.commit()

    new_id = cursor.lastrowid

    cursor.close()

    return {
        "message": "Product created successfully",
        "product_id": new_id
    }


# PUT - Update Product
@app.put("/products/{product_id}")
def update_product(product_id: int, product: Product):

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

    cursor.execute(query, values)

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


# DELETE - Delete Product
@app.delete("/products/{product_id}")
def delete_product(product_id: int):

    cursor = conn.cursor()

    query = """
        DELETE FROM products
        WHERE product_id = %s
    """

    cursor.execute(query, (product_id,))

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