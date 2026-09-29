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
    customer_token VARCHAR(255) NOT NULL UNIQUE,
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
-- 1. CUSTOMERS - 5 SAMPLE RECORDS
-- ============================================================

INSERT INTO customers (name, email, customer_token)
SELECT 'Rahul Sharma', 'rahul@example.com', UUID()
WHERE NOT EXISTS (
    SELECT 1 FROM customers WHERE email = 'rahul@example.com'
);

INSERT INTO customers (name, email, customer_token)
SELECT 'Priya Reddy', 'priya@example.com', UUID()
WHERE NOT EXISTS (
    SELECT 1 FROM customers WHERE email = 'priya@example.com'
);

INSERT INTO customers (name, email, customer_token)
SELECT 'Arjun Kumar', 'arjun@example.com', UUID()
WHERE NOT EXISTS (
    SELECT 1 FROM customers WHERE email = 'arjun@example.com'
);

INSERT INTO customers (name, email, customer_token)
SELECT 'Sneha Patel', 'sneha@example.com', UUID()
WHERE NOT EXISTS (
    SELECT 1 FROM customers WHERE email = 'sneha@example.com'
);

INSERT INTO customers (name, email, customer_token)
SELECT 'Kiran Rao', 'kiran@example.com', UUID()
WHERE NOT EXISTS (
    SELECT 1 FROM customers WHERE email = 'kiran@example.com'
);


-- ============================================================
-- 2. PRODUCTS - 5 SAMPLE RECORDS
-- ============================================================

INSERT INTO products
    (name, description, price, category, stock_count)
SELECT
    'iPhone 15',
    'Apple smartphone with advanced camera',
    69999.00,
    'Electronics',
    10
WHERE NOT EXISTS (
    SELECT 1 FROM products WHERE name = 'iPhone 15'
);

INSERT INTO products
    (name, description, price, category, stock_count)
SELECT
    'Samsung Galaxy S24',
    'Samsung flagship smartphone',
    64999.00,
    'Electronics',
    8
WHERE NOT EXISTS (
    SELECT 1 FROM products WHERE name = 'Samsung Galaxy S24'
);

INSERT INTO products
    (name, description, price, category, stock_count)
SELECT
    'Dell Laptop',
    'Business laptop for everyday use',
    55999.00,
    'Computers',
    5
WHERE NOT EXISTS (
    SELECT 1 FROM products WHERE name = 'Dell Laptop'
);

INSERT INTO products
    (name, description, price, category, stock_count)
SELECT
    'Wireless Headphones',
    'Bluetooth noise cancelling headphones',
    4999.00,
    'Accessories',
    15
WHERE NOT EXISTS (
    SELECT 1 FROM products WHERE name = 'Wireless Headphones'
);

INSERT INTO products
    (name, description, price, category, stock_count)
SELECT
    'Smart Watch',
    'Fitness and health tracking smartwatch',
    8999.00,
    'Accessories',
    12
WHERE NOT EXISTS (
    SELECT 1 FROM products WHERE name = 'Smart Watch'
);


-- ============================================================
-- 3. ORDERS - 5 SAMPLE RECORDS
-- ============================================================

INSERT INTO orders
    (customer_id, status, total_amount)
SELECT
    c.customer_id,
    'PLACED',
    69999.00
FROM customers c
WHERE c.email = 'rahul@example.com'
  AND NOT EXISTS (
      SELECT 1
      FROM orders o
      WHERE o.customer_id = c.customer_id
  );

INSERT INTO orders
    (customer_id, status, total_amount)
SELECT
    c.customer_id,
    'CONFIRMED',
    64999.00
FROM customers c
WHERE c.email = 'priya@example.com'
  AND NOT EXISTS (
      SELECT 1
      FROM orders o
      WHERE o.customer_id = c.customer_id
  );

INSERT INTO orders
    (customer_id, status, total_amount)
SELECT
    c.customer_id,
    'PLACED',
    111998.00
FROM customers c
WHERE c.email = 'arjun@example.com'
  AND NOT EXISTS (
      SELECT 1
      FROM orders o
      WHERE o.customer_id = c.customer_id
  );

INSERT INTO orders
    (customer_id, status, total_amount)
SELECT
    c.customer_id,
    'CANCELLED',
    4999.00
FROM customers c
WHERE c.email = 'sneha@example.com'
  AND NOT EXISTS (
      SELECT 1
      FROM orders o
      WHERE o.customer_id = c.customer_id
  );

INSERT INTO orders
    (customer_id, status, total_amount)
SELECT
    c.customer_id,
    'FAILED',
    8999.00
FROM customers c
WHERE c.email = 'kiran@example.com'
  AND NOT EXISTS (
      SELECT 1
      FROM orders o
      WHERE o.customer_id = c.customer_id
  );


-- ============================================================
-- 4. ORDER ITEMS - 5 SAMPLE RECORDS
-- ============================================================

INSERT INTO order_items
    (order_id, product_id, quantity, unit_price)
SELECT
    o.order_id,
    p.product_id,
    1,
    p.price
FROM orders o
JOIN customers c
    ON o.customer_id = c.customer_id
JOIN products p
    ON p.name = 'iPhone 15'
WHERE c.email = 'rahul@example.com'
  AND NOT EXISTS (
      SELECT 1
      FROM order_items oi
      WHERE oi.order_id = o.order_id
  );

INSERT INTO order_items
    (order_id, product_id, quantity, unit_price)
SELECT
    o.order_id,
    p.product_id,
    1,
    p.price
FROM orders o
JOIN customers c
    ON o.customer_id = c.customer_id
JOIN products p
    ON p.name = 'Samsung Galaxy S24'
WHERE c.email = 'priya@example.com'
  AND NOT EXISTS (
      SELECT 1
      FROM order_items oi
      WHERE oi.order_id = o.order_id
  );

INSERT INTO order_items
    (order_id, product_id, quantity, unit_price)
SELECT
    o.order_id,
    p.product_id,
    2,
    p.price
FROM orders o
JOIN customers c
    ON o.customer_id = c.customer_id
JOIN products p
    ON p.name = 'Dell Laptop'
WHERE c.email = 'arjun@example.com'
  AND NOT EXISTS (
      SELECT 1
      FROM order_items oi
      WHERE oi.order_id = o.order_id
  );

INSERT INTO order_items
    (order_id, product_id, quantity, unit_price)
SELECT
    o.order_id,
    p.product_id,
    1,
    p.price
FROM orders o
JOIN customers c
    ON o.customer_id = c.customer_id
JOIN products p
    ON p.name = 'Wireless Headphones'
WHERE c.email = 'sneha@example.com'
  AND NOT EXISTS (
      SELECT 1
      FROM order_items oi
      WHERE oi.order_id = o.order_id
  );

INSERT INTO order_items
    (order_id, product_id, quantity, unit_price)
SELECT
    o.order_id,
    p.product_id,
    1,
    p.price
FROM orders o
JOIN customers c
    ON o.customer_id = c.customer_id
JOIN products p
    ON p.name = 'Smart Watch'
WHERE c.email = 'kiran@example.com'
  AND NOT EXISTS (
      SELECT 1
      FROM order_items oi
      WHERE oi.order_id = o.order_id
  );


-- ============================================================
-- 5. HISTORY - 5 SAMPLE RECORDS
-- ============================================================

INSERT INTO history
    (order_id, old_status, new_status, changed_by)
SELECT
    o.order_id,
    NULL,
    'PLACED',
    'seed-data'
FROM orders o
JOIN customers c
    ON o.customer_id = c.customer_id
WHERE c.email = 'rahul@example.com'
  AND NOT EXISTS (
      SELECT 1
      FROM history h
      WHERE h.order_id = o.order_id
  );

INSERT INTO history
    (order_id, old_status, new_status, changed_by)
SELECT
    o.order_id,
    'PLACED',
    'CONFIRMED',
    'seed-data'
FROM orders o
JOIN customers c
    ON o.customer_id = c.customer_id
WHERE c.email = 'priya@example.com'
  AND NOT EXISTS (
      SELECT 1
      FROM history h
      WHERE h.order_id = o.order_id
  );

INSERT INTO history
    (order_id, old_status, new_status, changed_by)
SELECT
    o.order_id,
    NULL,
    'PLACED',
    'seed-data'
FROM orders o
JOIN customers c
    ON o.customer_id = c.customer_id
WHERE c.email = 'arjun@example.com'
  AND NOT EXISTS (
      SELECT 1
      FROM history h
      WHERE h.order_id = o.order_id
  );

INSERT INTO history
    (order_id, old_status, new_status, changed_by)
SELECT
    o.order_id,
    'PLACED',
    'CANCELLED',
    'seed-data'
FROM orders o
JOIN customers c
    ON o.customer_id = c.customer_id
WHERE c.email = 'sneha@example.com'
  AND NOT EXISTS (
      SELECT 1
      FROM history h
      WHERE h.order_id = o.order_id
  );

INSERT INTO history
    (order_id, old_status, new_status, changed_by)
SELECT
    o.order_id,
    'PLACED',
    'FAILED',
    'seed-data'
FROM orders o
JOIN customers c
    ON o.customer_id = c.customer_id
WHERE c.email = 'kiran@example.com'
  AND NOT EXISTS (
      SELECT 1
      FROM history h
      WHERE h.order_id = o.order_id
  );


-- ============================================================
-- VERIFY SAMPLE DATA
-- ============================================================

SELECT * FROM customers;
SELECT * FROM products;
SELECT * FROM orders;
SELECT * FROM order_items;
SELECT * FROM history;

SHOW TABLES;
