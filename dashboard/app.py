import os
import pymysql
import boto3
import csv
import io
from flask import Flask, render_template, request, redirect, url_for, session
from functools import wraps
import hmac


app = Flask(__name__) # used to protect Flask sessions.

app.config["SECRET_KEY"] = os.environ["FLASK_SECRET_KEY"]


AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")
REPORTS_BUCKET = os.environ["REPORTS_BUCKET"]
ADMIN_TOKEN_PARAMETER = os.environ["ADMIN_TOKEN_PARAMETER"]


ssm = boto3.client(
    "ssm",
    region_name=AWS_REGION
)

s3 = boto3.client(
    "s3",
    region_name=AWS_REGION
)

# ============================================================
# SSM PARAMETER
# ============================================================

def get_parameter(name):

    response = ssm.get_parameter(
        Name=name,
        WithDecryption=True
    )

    return response["Parameter"]["Value"]
# ============================================================
# ADMIN AUTHENTICATION
# ============================================================

@app.before_request
def require_admin_login():

    allowed_endpoints = {
        "login",
        "health",
        "static"
    }

    if request.endpoint in allowed_endpoints:
        return

    if not session.get("admin_authenticated"):
        return redirect(
            url_for(
                "login",
                next=request.url
            )
        )


@app.route("/login", methods=["GET", "POST"])
def login():

    if session.get("admin_authenticated"):
        return redirect(url_for("dashboard"))

    error = None

    if request.method == "POST":

        entered_token = request.form.get(
            "admin_token",
            ""
        ).strip()

        try:

            stored_token = get_parameter(
                ADMIN_TOKEN_PARAMETER
            )

            if hmac.compare_digest(
                entered_token,
                stored_token
            ):

                session["admin_authenticated"] = True

                next_url = request.args.get("next")

                if next_url and next_url.startswith("/"):
                    return redirect(next_url)

                return redirect(
                    url_for("dashboard")
                )

            error = "Invalid Admin Token"

        except Exception:

            error = "Unable to validate Admin Token"

    return render_template(
        "login.html",
        error=error
    )
# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db_connection():

    return pymysql.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "3306")),
        user=get_parameter(
            os.environ["DB_USERNAME_PARAMETER"]
        ),
        password=get_parameter(
            os.environ["DB_PASSWORD_PARAMETER"]
        ),
        database=os.environ.get(
            "DB_NAME",
            "cloudmart"
        ),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )


# ============================================================
# DATABASE QUERY HELPER
# ============================================================

def query_db(sql, params=None):

    connection = None

    try:

        connection = get_db_connection()

        with connection.cursor() as cursor:

            cursor.execute(
                sql,
                params or ()
            )

            return cursor.fetchall()

    finally:

        if connection:
            connection.close()
# ============================================================
# PAGINATION
# ============================================================

def get_pagination():
    page = request.args.get("page", 1, type=int)

    if page < 1:
        page = 1

    per_page = 10
    offset = (page - 1) * per_page

    return page, per_page, offset


# ============================================================
# DASHBOARD
# ============================================================

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


# ============================================================
# PRODUCTS
# ============================================================

@app.route("/products")
def products():

    search = request.args.get("search", "").strip()

    page = request.args.get("page", 1, type=int)

    if page < 1:
        page = 1

    per_page = 10
    offset = (page - 1) * per_page

    search_pattern = f"%{search}%"

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
            LIMIT %s OFFSET %s
            """,
            (
                search_pattern,
                search_pattern,
                search_pattern,
                per_page,
                offset
            )
        )

        total_result = query_db(
            """
            SELECT COUNT(*) AS total
            FROM products
            WHERE soft_delete IS NULL
              AND (
                  name LIKE %s
                  OR category LIKE %s
                  OR description LIKE %s
              )
            """,
            (
                search_pattern,
                search_pattern,
                search_pattern
            )
        )

    else:

        products = query_db(
            """
            SELECT *
            FROM products
            WHERE soft_delete IS NULL
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            (per_page, offset)
        )

        total_result = query_db(
            """
            SELECT COUNT(*) AS total
            FROM products
            WHERE soft_delete IS NULL
            """
        )

    total_products = total_result[0]["total"]

    total_pages = max(1, (total_products + per_page - 1) // per_page)
    return render_template(
        "products.html",
        products=products,
        search=search,
        page=page,
        total_pages=total_pages
    )

# ============================================================
# CUSTOMERS
# ============================================================

@app.route("/customers")
def customers():

    search = request.args.get("search", "").strip()

    page, per_page, offset = get_pagination()

    if search:

        customers = query_db(
            """
            SELECT
                c.customer_id,
                c.name,
                c.email,
                c.created_at,
                COUNT(o.order_id) AS total_orders,
                COALESCE(
                    SUM(
                        CASE
                            WHEN o.status = 'CONFIRMED'
                            THEN o.total_amount
                            ELSE 0
                        END
                    ),
                    0
                ) AS total_spent
            FROM customers c
            LEFT JOIN orders o
                ON c.customer_id = o.customer_id
            WHERE
                c.name LIKE %s
                OR c.email LIKE %s
                OR CAST(c.customer_id AS CHAR) LIKE %s
            GROUP BY
                c.customer_id,
                c.name,
                c.email,
                c.created_at
            ORDER BY c.customer_id DESC
            LIMIT %s OFFSET %s
            """,
            (
                f"%{search}%",
                f"%{search}%",
                f"%{search}%",
                per_page,
                offset
            )
        )

        total_result = query_db(
            """
            SELECT COUNT(*) AS total
            FROM customers
            WHERE
                name LIKE %s
                OR email LIKE %s
                OR CAST(customer_id AS CHAR) LIKE %s
            """,
            (
                f"%{search}%",
                f"%{search}%",
                f"%{search}%"
            )
        )

    else:

        customers = query_db(
            """
            SELECT
                c.customer_id,
                c.name,
                c.email,
                c.created_at,
                COUNT(o.order_id) AS total_orders,
                COALESCE(
                    SUM(
                        CASE
                            WHEN o.status = 'CONFIRMED'
                            THEN o.total_amount
                            ELSE 0
                        END
                    ),
                    0
                ) AS total_spent
            FROM customers c
            LEFT JOIN orders o
                ON c.customer_id = o.customer_id
            GROUP BY
                c.customer_id,
                c.name,
                c.email,
                c.created_at
            ORDER BY c.customer_id DESC
            LIMIT %s OFFSET %s
            """,
            (
                per_page,
                offset
            )
        )

        total_result = query_db(
            """
            SELECT COUNT(*) AS total
            FROM customers
            """
        )

    total_customers = total_result[0]["total"]

    total_pages = max(
        1,
        (total_customers + per_page - 1) // per_page
    )
    return render_template(
    "customers.html",
    customers=customers,
    search=search,
    page=page,
    total_pages=total_pages
)

# ============================================================
# CUSTOMER DETAILS
# ============================================================

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


# ============================================================
# ORDERS
# ============================================================

@app.route("/orders")
def orders():

    search = request.args.get("search", "").strip()

    page, per_page, offset = get_pagination()

    if search:

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
            WHERE
                CAST(o.order_id AS CHAR) LIKE %s
                OR CAST(o.customer_id AS CHAR) LIKE %s
                OR c.name LIKE %s
                OR c.email LIKE %s
                OR o.status LIKE %s
            ORDER BY o.created_at DESC
            LIMIT %s OFFSET %s
            """,
            (
                f"%{search}%",
                f"%{search}%",
                f"%{search}%",
                f"%{search}%",
                f"%{search}%",
                per_page,
                offset
            )
        )

        total_result = query_db(
            """
            SELECT COUNT(*) AS total
            FROM orders o
            JOIN customers c
                ON o.customer_id = c.customer_id
            WHERE
                CAST(o.order_id AS CHAR) LIKE %s
                OR CAST(o.customer_id AS CHAR) LIKE %s
                OR c.name LIKE %s
                OR c.email LIKE %s
                OR o.status LIKE %s
            """,
            (
                f"%{search}%",
                f"%{search}%",
                f"%{search}%",
                f"%{search}%",
                f"%{search}%"
            )
        )

    else:

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
            LIMIT %s OFFSET %s
            """,
            (
                per_page,
                offset
            )
        )

        total_result = query_db(
            """
            SELECT COUNT(*) AS total
            FROM orders
            """
        )

    total_orders = total_result[0]["total"]

    total_pages = max(
        1,
        (total_orders + per_page - 1) // per_page
    )

    return render_template(
        "orders.html",
        orders=orders,
        search=search,
        page=page,
        total_pages=total_pages
    )


# ============================================================
# ORDER DETAILS
# ============================================================

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


# ============================================================
# ORDER ITEMS
# ============================================================

@app.route("/order-items")
def order_items():

    search = request.args.get("search", "").strip()

    page, per_page, offset = get_pagination()

    if search:

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
            WHERE
                CAST(oi.order_item_id AS CHAR) LIKE %s
                OR CAST(oi.order_id AS CHAR) LIKE %s
                OR CAST(oi.product_id AS CHAR) LIKE %s
                OR p.name LIKE %s
            ORDER BY oi.order_id DESC
            LIMIT %s OFFSET %s
            """,
            (
                f"%{search}%",
                f"%{search}%",
                f"%{search}%",
                f"%{search}%",
                per_page,
                offset
            )
        )

        total_result = query_db(
            """
            SELECT COUNT(*) AS total
            FROM order_items oi
            JOIN products p
                ON oi.product_id = p.product_id
            WHERE
                CAST(oi.order_item_id AS CHAR) LIKE %s
                OR CAST(oi.order_id AS CHAR) LIKE %s
                OR CAST(oi.product_id AS CHAR) LIKE %s
                OR p.name LIKE %s
            """,
            (
                f"%{search}%",
                f"%{search}%",
                f"%{search}%",
                f"%{search}%"
            )
        )

    else:

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
            LIMIT %s OFFSET %s
            """,
            (
                per_page,
                offset
            )
        )

        total_result = query_db(
            """
            SELECT COUNT(*) AS total
            FROM order_items
            """
        )

    total_items = total_result[0]["total"]

    total_pages = max(
        1,
        (total_items + per_page - 1) // per_page
    )

    return render_template(
        "order_items.html",
        items=items,
        search=search,
        page=page,
        total_pages=total_pages
    )
# ============================================================
# HISTORY
# ============================================================
@app.route("/history")
def history():

    search = request.args.get("search", "").strip()

    page, per_page, offset = get_pagination()

    if search:

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
            WHERE
                CAST(h.history_id AS CHAR) LIKE %s
                OR CAST(h.order_id AS CHAR) LIKE %s
                OR h.old_status LIKE %s
                OR h.new_status LIKE %s
                OR h.changed_by LIKE %s
            ORDER BY h.changed_at DESC
            LIMIT %s OFFSET %s
            """,
            (
                f"%{search}%",
                f"%{search}%",
                f"%{search}%",
                f"%{search}%",
                f"%{search}%",
                per_page,
                offset
            )
        )

        total_result = query_db(
            """
            SELECT COUNT(*) AS total
            FROM history h
            WHERE
                CAST(h.history_id AS CHAR) LIKE %s
                OR CAST(h.order_id AS CHAR) LIKE %s
                OR h.old_status LIKE %s
                OR h.new_status LIKE %s
                OR h.changed_by LIKE %s
            """,
            (
                f"%{search}%",
                f"%{search}%",
                f"%{search}%",
                f"%{search}%",
                f"%{search}%"
            )
        )

    else:

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
            LIMIT %s OFFSET %s
            """,
            (
                per_page,
                offset
            )
        )

        total_result = query_db(
            """
            SELECT COUNT(*) AS total
            FROM history
            """
        )

    total_history = total_result[0]["total"]

    total_pages = max(
        1,
        (total_history + per_page - 1) // per_page
    )

    return render_template(
        "history.html",
        history=history,
        search=search,
        page=page,
        total_pages=total_pages
    )
# ============================================================
# REPORTS
# ============================================================

@app.route("/reports")
def reports():

    response = s3.list_objects_v2(
        Bucket=REPORTS_BUCKET,
        Prefix="reports/"
    )

    reports = response.get(
        "Contents",
        []
    )

    reports.sort(
        key=lambda x: x["LastModified"],
        reverse=True
    )

    latest_report = (
        reports[0]
        if reports
        else None
    )

    return render_template(
        "reports.html",
        reports=reports,
        latest_report=latest_report
    )


# ============================================================
# VIEW REPORT
# ============================================================
@app.route("/reports/view")
def view_report():
    key = request.args.get("key", "")

    if not key or not key.startswith("reports/"):
        return "Invalid report", 400

    try:
        response = s3.get_object(
            Bucket=REPORTS_BUCKET,
            Key=key
        )

        csv_content = response["Body"].read().decode("utf-8")

        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)

        return render_template(
            "report_view.html",
            report_name=key.split("/")[-1],
            columns=reader.fieldnames or [],
            rows=rows
        )

    except Exception as error:
        return render_template("error.html", error=str(error)), 500


# ============================================================
# DOWNLOAD REPORT
# ============================================================

@app.route("/reports/download")
def download_report():

    key = request.args.get("key")

    if not key or not key.startswith("reports/"):

        return "Invalid report", 400

    filename = key.split("/")[-1]

    url = s3.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": REPORTS_BUCKET,
            "Key": key,
            "ResponseContentType": "text/csv",
            "ResponseContentDisposition": (
                f'attachment; filename="{filename}"'
            )
        },
        ExpiresIn=300
    )

    return redirect(url)

# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )
# ============================================================
# ERROR HANDLER
# ============================================================

@app.errorhandler(Exception)
def handle_error(error):

    return render_template(
        "error.html",
        error=str(error)
    ), 500
# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health")
def health():

    return {
        "status": "ok",
        "service": "cloudmart-dashboard"
    }, 200
# ============================================================
# LOCAL RUN
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )

