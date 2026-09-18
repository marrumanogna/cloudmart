import os
import pymysql
import boto3

from flask import Flask, render_template, request

app = Flask(__name__)

AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")
REPORTS_BUCKET = os.environ["REPORTS_BUCKET"]

ssm = boto3.client("ssm", region_name=AWS_REGION)
s3 = boto3.client("s3", region_name=AWS_REGION)


def get_parameter(name):
    response = ssm.get_parameter(
        Name=name,
        WithDecryption=True
    )
    return response["Parameter"]["Value"]


def get_db_connection():
    return pymysql.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "3306")),
        user=get_parameter(os.environ["DB_USERNAME_PARAMETER"]),
        password=get_parameter(os.environ["DB_PASSWORD_PARAMETER"]),
        database=os.environ.get("DB_NAME", "cloudmart"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )


def query_db(sql, params=None):
    connection = None

    try:
        connection = get_db_connection()

        with connection.cursor() as cursor:
            cursor.execute(sql, params or ())
            return cursor.fetchall()

    finally:
        if connection:
            connection.close()


@app.route("/")
def dashboard():

    total_products = query_db(
        """
        SELECT COUNT(*) AS count
        FROM products
        WHERE soft_delete IS NULL
        """
    )[0]["count"]

    total_customers = query_db(
        "SELECT COUNT(*) AS count FROM customers"
    )[0]["count"]

    total_orders = query_db(
        "SELECT COUNT(*) AS count FROM orders"
    )[0]["count"]

    total_revenue = query_db(
        """
        SELECT COALESCE(SUM(total_amount), 0) AS revenue
        FROM orders
        WHERE status = 'CONFIRMED'
        """
    )[0]["revenue"]

    low_stock = query_db(
        """
        SELECT COUNT(*) AS count
        FROM products
        WHERE soft_delete IS NULL
        AND stock_count > 0
        AND stock_count <= 10
        """
    )[0]["count"]

    failed_orders = query_db(
        """
        SELECT COUNT(*) AS count
        FROM orders
        WHERE status = 'FAILED'
        """
    )[0]["count"]

    best_selling = query_db(
        """
        SELECT
            p.product_id,
            p.name,
            p.category,
            p.price,
            p.stock_count,
            COALESCE(SUM(oi.quantity), 0) AS units_sold
        FROM products p
        LEFT JOIN order_items oi
            ON p.product_id = oi.product_id
        LEFT JOIN orders o
            ON oi.order_id = o.order_id
            AND o.status = 'CONFIRMED'
        WHERE p.soft_delete IS NULL
        GROUP BY
            p.product_id,
            p.name,
            p.category,
            p.price,
            p.stock_count
        ORDER BY units_sold DESC
        LIMIT 10
        """
    )

    recent_orders = query_db(
        """
        SELECT
            o.order_id,
            o.customer_id,
            c.name AS customer_name,
            o.status,
            o.total_amount,
            o.created_at
        FROM orders o
        JOIN customers c
            ON o.customer_id = c.customer_id
        ORDER BY o.created_at DESC
        LIMIT 10
        """
    )

    return render_template(
        "dashboard.html",
        total_products=total_products,
        total_customers=total_customers,
        total_orders=total_orders,
        total_revenue=total_revenue,
        low_stock=low_stock,
        failed_orders=failed_orders,
        best_selling=best_selling,
        recent_orders=recent_orders
    )


@app.route("/products")
def products():

    search = request.args.get("search", "").strip()

    if search:

        products = query_db(
            """
            SELECT *
            FROM products
            WHERE soft_delete IS NULL
            AND (
                name LIKE %s
                OR category LIKE %s
                OR description LIKE %s
            )
            ORDER BY created_at DESC
            """,
            (
                f"%{search}%",
                f"%{search}%",
                f"%{search}%"
            )
        )

    else:

        products = query_db(
            """
            SELECT *
            FROM products
            WHERE soft_delete IS NULL
            ORDER BY created_at DESC
            """
        )

    return render_template(
        "products.html",
        products=products,
        search=search
    )


@app.route("/customers")
def customers():

    customers = query_db(
        """
        SELECT
            c.customer_id,
            c.name,
            c.email,
            c.created_at,
            COUNT(o.order_id) AS total_orders,
            COALESCE(SUM(
                CASE
                    WHEN o.status = 'CONFIRMED'
                    THEN o.total_amount
                    ELSE 0
                END
            ), 0) AS total_spent
        FROM customers c
        LEFT JOIN orders o
            ON c.customer_id = o.customer_id
        GROUP BY
            c.customer_id,
            c.name,
            c.email,
            c.created_at
        ORDER BY c.customer_id DESC
        """
    )

    return render_template(
        "customers.html",
        customers=customers
    )


@app.route("/customers/<int:customer_id>")
def customer_details(customer_id):

    customer = query_db(
        """
        SELECT *
        FROM customers
        WHERE customer_id = %s
        """,
        (customer_id,)
    )

    if not customer:
        return render_template(
            "error.html",
            error="Customer not found"
        ), 404

    orders = query_db(
        """
        SELECT
            order_id,
            status,
            total_amount,
            created_at,
            updated_at
        FROM orders
        WHERE customer_id = %s
        ORDER BY created_at DESC
        """,
        (customer_id,)
    )

    return render_template(
        "customer_details.html",
        customer=customer[0],
        orders=orders
    )


@app.route("/orders")
def orders():

    orders = query_db(
        """
        SELECT
            o.order_id,
            o.customer_id,
            c.name AS customer_name,
            c.email AS customer_email,
            o.status,
            o.total_amount,
            o.created_at,
            o.updated_at
        FROM orders o
        JOIN customers c
            ON o.customer_id = c.customer_id
        ORDER BY o.created_at DESC
        """
    )

    return render_template(
        "orders.html",
        orders=orders
    )


@app.route("/orders/<int:order_id>")
def order_details(order_id):

    order = query_db(
        """
        SELECT
            o.*,
            c.name AS customer_name,
            c.email AS customer_email
        FROM orders o
        JOIN customers c
            ON o.customer_id = c.customer_id
        WHERE o.order_id = %s
        """,
        (order_id,)
    )

    if not order:
        return render_template(
            "error.html",
            error="Order not found"
        ), 404

    items = query_db(
        """
        SELECT
            oi.order_item_id,
            oi.order_id,
            oi.product_id,
            p.name AS product_name,
            oi.quantity,
            oi.unit_price,
            (oi.quantity * oi.unit_price) AS item_total
        FROM order_items oi
        JOIN products p
            ON oi.product_id = p.product_id
        WHERE oi.order_id = %s
        """,
        (order_id,)
    )

    return render_template(
        "order_details.html",
        order=order[0],
        items=items
    )


@app.route("/order-items")
def order_items():

    items = query_db(
        """
        SELECT
            oi.order_item_id,
            oi.order_id,
            oi.product_id,
            p.name AS product_name,
            oi.quantity,
            oi.unit_price,
            (oi.quantity * oi.unit_price) AS item_total
        FROM order_items oi
        JOIN products p
            ON oi.product_id = p.product_id
        ORDER BY oi.order_id DESC
        """
    )

    return render_template(
        "order_items.html",
        items=items
    )


@app.route("/history")
def history():

    history = query_db(
        """
        SELECT
            h.history_id,
            h.order_id,
            h.old_status,
            h.new_status,
            h.changed_at,
            h.changed_by
        FROM history h
        ORDER BY h.changed_at DESC
        """
    )

    return render_template(
        "history.html",
        history=history
    )


@app.route("/reports")
def reports():

    response = s3.list_objects_v2(
        Bucket=REPORTS_BUCKET,
        Prefix="reports/"
    )

    reports = response.get("Contents", [])

    reports.sort(
        key=lambda x: x["LastModified"],
        reverse=True
    )

    return render_template(
        "reports.html",
        reports=reports
    )


@app.errorhandler(Exception)
def handle_error(error):

    return render_template(
        "error.html",
        error=str(error)
    ), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )