import json
import os
import boto3
import pymysql

ssm = boto3.client("ssm")
events = boto3.client("events")
sns = boto3.client("sns")

LOW_STOCK_THRESHOLD = 5


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


def log_success(action, product_id=None, details=None):
    log_data = {
        "level": "INFO",
        "event": "PRODUCT_OPERATION_SUCCESS",
        "action": action,
        "environment": os.environ.get("ENVIRONMENT", "unknown")
    }

    if product_id is not None:
        log_data["product_id"] = int(product_id)

    if details:
        log_data.update(details)

    print(json.dumps(log_data, default=str))


def publish_inventory_event(action, product):
    event_detail = {
        "action": action,
        "product_id": int(product["product_id"]),
        "name": product.get("name"),
        "category": product.get("category"),
        "price": str(product.get("price")),
        "stock_count": int(product.get("stock_count", 0))
    }

    response_data = events.put_events(
        Entries=[
            {
                "EventBusName": os.environ["EVENT_BUS_NAME"],
                "Source": "cloudmart.product",
                "DetailType": "Inventory Change",
                "Detail": json.dumps(event_detail)
            }
        ]
    )

    if response_data.get("FailedEntryCount", 0) > 0:
        raise Exception(
            f"EventBridge failed to publish inventory event: {response_data}"
        )

    print(json.dumps({
        "level": "INFO",
        "event": "INVENTORY_EVENT_PUBLISHED",
        "action": action,
        "product_id": int(product["product_id"])
    }))


def publish_low_stock_alert(product):
    stock_count = int(product.get("stock_count", 0))

    if stock_count > LOW_STOCK_THRESHOLD:
        return

    message = (
        f"CloudMart Low Stock Alert\n\n"
        f"Product ID: {product['product_id']}\n"
        f"Product Name: {product.get('name')}\n"
        f"Category: {product.get('category')}\n"
        f"Current Stock: {stock_count}\n"
        f"Low Stock Threshold: {LOW_STOCK_THRESHOLD}\n"
    )

    sns.publish(
        TopicArn=os.environ["LOW_STOCK_TOPIC_ARN"],
        Subject="CloudMart Low Stock Alert",
        Message=message
    )

    print(json.dumps({
        "level": "INFO",
        "event": "LOW_STOCK_ALERT_PUBLISHED",
        "product_id": int(product["product_id"]),
        "stock_count": stock_count,
        "threshold": LOW_STOCK_THRESHOLD
    }))


def get_product_by_id(connection, product_id):
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

        return cursor.fetchone()


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

            log_success(
                "GET_PRODUCTS",
                details={"count": len(products)}
            )

            return response(
                200,
                "Products retrieved successfully",
                {"products": products}
            )

        # =====================================================
        # GET /products/{id}
        # =====================================================

        if method == "GET" and product_id:

            product = get_product_by_id(
                connection,
                product_id
            )

            if not product:
                return response(
                    404,
                    "Product not found"
                )

            log_success(
                "GET_PRODUCT",
                product_id
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

            body = json.loads(
                event.get("body") or "{}"
            )

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

            try:
                stock_count = int(stock_count)
            except (TypeError, ValueError):
                return response(
                    400,
                    "stock_count must be a number"
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

            product = get_product_by_id(
                connection,
                product_id
            )

            publish_inventory_event(
                "PRODUCT_CREATED",
                product
            )

            publish_low_stock_alert(
                product
            )

            log_success(
                "CREATE_PRODUCT",
                product_id,
                {
                    "stock_count": stock_count
                }
            )

            return response(
                201,
                "Product created successfully",
                {"product_id": product_id}
            )

        # =====================================================
        # PUT /products/{id}
        # =====================================================

        if method == "PUT" and product_id:

            body = json.loads(
                event.get("body") or "{}"
            )

            name = body.get("name")
            description = body.get("description")
            price = body.get("price")
            category = body.get("category")
            stock_count = body.get("stock_count")

            if (
                name is None
                and description is None
                and price is None
                and category is None
                and stock_count is None
            ):
                return response(
                    400,
                    "At least one field is required for update"
                )

            if stock_count is not None:
                try:
                    stock_count = int(stock_count)
                except (TypeError, ValueError):
                    return response(
                        400,
                        "stock_count must be a number"
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

                cursor.execute(
                    query,
                    values
                )

            connection.commit()

            product = get_product_by_id(
                connection,
                product_id
            )

            publish_inventory_event(
                "PRODUCT_UPDATED",
                product
            )

            publish_low_stock_alert(
                product
            )

            log_success(
                "UPDATE_PRODUCT",
                product_id,
                {
                    "stock_count": int(
                        product["stock_count"]
                    )
                }
            )

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
                    SELECT
                        product_id,
                        name,
                        description,
                        price,
                        category,
                        stock_count
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

            publish_inventory_event(
                "PRODUCT_DELETED",
                existing
            )

            log_success(
                "DELETE_PRODUCT",
                product_id
            )

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
            "event": "PRODUCT_OPERATION_FAILED",
            "message": "Product Lambda error",
            "error": str(e),
            "method": event.get("httpMethod"),
            "path": event.get("path"),
            "request_id": context.aws_request_id
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