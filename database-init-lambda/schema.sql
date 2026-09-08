-- ============================================================
-- CloudMart Database Schema
-- Database: cloudmart
-- ============================================================

CREATE DATABASE IF NOT EXISTS cloudmart;

USE cloudmart;


-- ============================================================
-- 1. CUSTOMERS
-- ============================================================

CREATE TABLE IF NOT EXISTS customers (
    customer_id INT AUTO_INCREMENT PRIMARY KEY,

    name VARCHAR(150) NOT NULL,

    email VARCHAR(150) NOT NULL UNIQUE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 2. PRODUCTS
-- ============================================================

CREATE TABLE IF NOT EXISTS products (
    product_id INT AUTO_INCREMENT PRIMARY KEY,

    name VARCHAR(200) NOT NULL,

    description TEXT NULL,

    price DECIMAL(10,2) NOT NULL,

    category VARCHAR(100) NOT NULL,

    stock_count INT NOT NULL DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    soft_delete TIMESTAMP NULL,

    INDEX idx_products_name (name),

    INDEX idx_products_category (category)
);


-- ============================================================
-- 3. ORDERS
-- ============================================================

CREATE TABLE IF NOT EXISTS orders (
    order_id INT AUTO_INCREMENT PRIMARY KEY,

    customer_id INT NOT NULL,

    status ENUM(
        'PLACED',
        'CONFIRMED',
        'FAILED',
        'CANCELLED'
    ) NOT NULL,

    total_amount DECIMAL(10,2) NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT fk_orders_customer
        FOREIGN KEY (customer_id)
        REFERENCES customers(customer_id),

    INDEX idx_orders_customer_id (customer_id),

    INDEX idx_orders_status (status),

    INDEX idx_orders_created_at (created_at),

    INDEX idx_orders_customer_created (
        customer_id,
        created_at
    )
);


-- ============================================================
-- 4. ORDER ITEMS
-- ============================================================

CREATE TABLE IF NOT EXISTS order_items (
    order_item_id INT AUTO_INCREMENT PRIMARY KEY,

    order_id INT NOT NULL,

    product_id INT NOT NULL,

    quantity INT NOT NULL,

    unit_price DECIMAL(10,2) NOT NULL,

    CONSTRAINT fk_order_items_order
        FOREIGN KEY (order_id)
        REFERENCES orders(order_id),

    CONSTRAINT fk_order_items_product
        FOREIGN KEY (product_id)
        REFERENCES products(product_id),

    INDEX idx_order_items_order_id (order_id),

    INDEX idx_order_items_product_id (product_id)
);


-- ============================================================
-- 5. HISTORY
-- ============================================================

CREATE TABLE IF NOT EXISTS history (
    history_id INT AUTO_INCREMENT PRIMARY KEY,

    order_id INT NOT NULL,

    old_status VARCHAR(30) NULL,

    new_status VARCHAR(30) NOT NULL,

    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    changed_by VARCHAR(100) NULL,

    CONSTRAINT fk_history_order
        FOREIGN KEY (order_id)
        REFERENCES orders(order_id)
);


-- ============================================================
-- VERIFY TABLES
-- ============================================================

SHOW TABLES;