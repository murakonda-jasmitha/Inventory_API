CREATE DATABASE IF NOT EXISTS myinventory_db;

USE myinventory_db;

CREATE TABLE IF NOT EXISTS products (
    product_id INT AUTO_INCREMENT PRIMARY KEY,
    product_name VARCHAR(100) NOT NULL,
    sell_price DECIMAL(10,2) NOT NULL,
    quantity INT NOT NULL
);