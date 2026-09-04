import json
import os
import boto3
import pymysql

ssm = boto3.client("ssm")


def get_db_connection():
    username = ssm.get_parameter(
        Name=os.environ["DB_USERNAME_PARAMETER"],
        WithDecryption=True
    )["Parameter"]["Value"]

    password = ssm.get_parameter(
        Name=os.environ["DB_PASSWORD_PARAMETER"],
        WithDecryption=True
    )["Parameter"]["Value"]

    return pymysql.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ["DB_PORT"]),
        user=username,
        password=password,
        database=os.environ["DB_NAME"],
        connect_timeout=10,
        cursorclass=pymysql.cursors.DictCursor
    )


def response(status_code, message, data=None):
    body = {"message": message}

    if data is not None:
        body.update(data)

    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(body, default=str)
    }


def lambda_handler(event, context):

    connection = None

    try:
        method = event.get("httpMethod", "")
        path_parameters = event.get("pathParameters") or {}
        product_id = path_parameters.get("id")

        connection = get_db_connection()

        # =====================================================
        # GET /products
        # =====================================================
        if method == "GET" and not product_id:

            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT
                        product_id,
                        name,
                        description,
                        price,
                        category,
                        stock_count,
                        created_at,
                        updated_at
                    FROM products
                    WHERE soft_delete IS NULL
                    ORDER BY product_id
                """)

                products = cursor.fetchall()

            return response(
                200,
                "Products retrieved successfully",
                {"products": products}
            )

        # =====================================================
        # GET /products/{id}
        # =====================================================
        if method == "GET" and product_id:

            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT
                        product_id,
                        name,
                        description,
                        price,
                        category,
                        stock_count,
                        created_at,
                        updated_at
                    FROM products
                    WHERE product_id = %s
                    AND soft_delete IS NULL
                """, (product_id,))

                product = cursor.fetchone()

            if not product:
                return response(
                    404,
                    "Product not found"
                )

            return response(
                200,
                "Product retrieved successfully",
                {"product": product}
            )

        # =====================================================
        # POST /products
        # =====================================================
        if method == "POST":

            body = json.loads(event.get("body") or "{}")

            name = body.get("name")
            description = body.get("description")
            price = body.get("price")
            category = body.get("category")
            stock_count = body.get("stock_count", 0)

            if not name or price is None or not category:
                return response(
                    400,
                    "name, price and category are required"
                )

            with connection.cursor() as cursor:

                cursor.execute("""
                    INSERT INTO products
                    (
                        name,
                        description,
                        price,
                        category,
                        stock_count
                    )
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    name,
                    description,
                    price,
                    category,
                    stock_count
                ))

                product_id = cursor.lastrowid

            connection.commit()

            return response(
                201,
                "Product created successfully",
                {"product_id": product_id}
            )

        # =====================================================
        # PUT /products/{id}
        # =====================================================
        if method == "PUT" and product_id:

            body = json.loads(event.get("body") or "{}")

            name = body.get("name")
            description = body.get("description")
            price = body.get("price")
            category = body.get("category")
            stock_count = body.get("stock_count")

            # Reject negative stock
            if stock_count is not None and stock_count < 0:
                return response(
                    400,
                    "Stock must be 0 or greater"
                )

            if (
                name is None
                and description is None
                and price is None
                and category is None
                and stock_count is None
            ):
                return response(
                    400,
                    "Stock must be positive"
                )

            fields = []
            values = []

            if name is not None:
                fields.append("name = %s")
                values.append(name)

            if description is not None:
                fields.append("description = %s")
                values.append(description)

            if price is not None:
                fields.append("price = %s")
                values.append(price)

            if category is not None:
                fields.append("category = %s")
                values.append(category)

            if stock_count is not None:
                fields.append("stock_count = %s")
                values.append(stock_count)

            values.append(product_id)

            with connection.cursor() as cursor:

                cursor.execute("""
                    SELECT product_id
                    FROM products
                    WHERE product_id = %s
                    AND soft_delete IS NULL
                """, (product_id,))

                existing = cursor.fetchone()

                if not existing:
                    return response(
                        404,
                        "Product not found"
                    )

                query = f"""
                    UPDATE products
                    SET {", ".join(fields)}
                    WHERE product_id = %s
                    AND soft_delete IS NULL
                """

                cursor.execute(query, values)

            connection.commit()

            return response(
                200,
                "Product updated successfully",
                {"product_id": int(product_id)}
            )

        # =====================================================
        # DELETE /products/{id}
        # =====================================================
        if method == "DELETE" and product_id:

            with connection.cursor() as cursor:

                cursor.execute("""
                    SELECT product_id
                    FROM products
                    WHERE product_id = %s
                    AND soft_delete IS NULL
                """, (product_id,))

                existing = cursor.fetchone()

                if not existing:
                    return response(
                        404,
                        "Product not found"
                    )

                cursor.execute("""
                    UPDATE products
                    SET soft_delete = CURRENT_TIMESTAMP
                    WHERE product_id = %s
                """, (product_id,))

            connection.commit()

            return response(
                200,
                "Product deleted successfully",
                {"product_id": int(product_id)}
            )

        return response(
            405,
            "Method not supported"
        )

    except Exception as e:

        print(json.dumps({
            "level": "ERROR",
            "message": "Product Lambda error",
            "error": str(e),
            "method": event.get("httpMethod"),
            "path": event.get("path")
        }))

        if connection:
            connection.rollback()

        return response(
            500,
            "Internal server error"
        )

    finally:

        if connection:
            connection.close()