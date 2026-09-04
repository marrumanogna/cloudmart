import json
import os
import boto3
import pymysql


ssm = boto3.client("ssm")
sqs = boto3.client("sqs")
events_client = boto3.client("events")


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
    body = {
        "message": message
    }

    if data is not None:
        body.update(data)

    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(body, default=str)
    }


def publish_event(detail_type, detail):
    try:
        events_client.put_events(
            Entries=[
                {
                    "Source": "cloudmart.order",
                    "DetailType": detail_type,
                    "Detail": json.dumps(detail, default=str),
                    "EventBusName": os.environ["EVENT_BUS_NAME"]
                }
            ]
        )

    except Exception as e:
        print(json.dumps({
            "level": "ERROR",
            "message": "EventBridge publish failed",
            "event_type": detail_type,
            "error": str(e)
        }))


def send_failed_order_to_sqs(order_data):
    sqs.send_message(
        QueueUrl=os.environ["FAILED_ORDERS_QUEUE_URL"],
        MessageBody=json.dumps(order_data, default=str)
    )


def lambda_handler(event, context):

    connection = None
    order_id = None

    try:

        record = event["Records"][0]
        message = json.loads(record["body"])

        if message.get("action") != "PROCESS_ORDER":
            return response(
                400,
                "Invalid order processor action"
            )

        customer_id = message.get("customer_id")
        items = message.get("items")

        if not customer_id:
            return response(
                400,
                "customer_id is required"
            )

        if not items or not isinstance(items, list):
            return response(
                400,
                "items must be a non-empty list"
            )

        connection = get_db_connection()

        # =====================================================
        # Validate Customer
        # =====================================================

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT customer_id
                FROM customers
                WHERE customer_id = %s
                """,
                (customer_id,)
            )

            customer = cursor.fetchone()

        if not customer:

            failed_data = {
                "customer_id": customer_id,
                "items": items,
                "reason": "Customer not found"
            }

            send_failed_order_to_sqs(failed_data)

            publish_event(
                "OrderFailed",
                failed_data
            )

            return response(
                404,
                "Customer not found"
            )

        # =====================================================
        # Validate Products and Stock
        # =====================================================

        total_amount = 0
        validated_items = []

        with connection.cursor() as cursor:

            for item in items:

                product_id = item.get("product_id")
                quantity = int(item.get("quantity", 0))

                if not product_id or quantity <= 0:

                    connection.rollback()

                    failed_data = {
                        "customer_id": customer_id,
                        "items": items,
                        "reason": "Invalid product_id or quantity"
                    }

                    send_failed_order_to_sqs(failed_data)

                    publish_event(
                        "OrderFailed",
                        failed_data
                    )

                    return response(
                        400,
                        "Invalid product_id or quantity"
                    )

                cursor.execute(
                    """
                    SELECT
                        product_id,
                        name,
                        price,
                        stock_count
                    FROM products
                    WHERE product_id = %s
                    AND soft_delete IS NULL
                    FOR UPDATE
                    """,
                    (product_id,)
                )

                product = cursor.fetchone()

                if not product:

                    connection.rollback()

                    failed_data = {
                        "customer_id": customer_id,
                        "items": items,
                        "reason": "Product not found",
                        "product_id": product_id
                    }

                    send_failed_order_to_sqs(failed_data)

                    publish_event(
                        "OrderFailed",
                        failed_data
                    )

                    return response(
                        404,
                        "Product not found"
                    )

                if product["stock_count"] < quantity:

                    connection.rollback()

                    failed_data = {
                        "customer_id": customer_id,
                        "items": items,
                        "reason": "Insufficient stock",
                        "product_id": product_id,
                        "requested_quantity": quantity,
                        "available_stock": product["stock_count"]
                    }

                    send_failed_order_to_sqs(failed_data)

                    publish_event(
                        "OrderFailed",
                        failed_data
                    )

                    return response(
                        409,
                        "Insufficient stock"
                    )

                item_total = (
                    product["price"] * quantity
                )

                total_amount += item_total

                validated_items.append({
                    "product_id": product_id,
                    "quantity": quantity,
                    "unit_price": product["price"]
                })

        # =====================================================
        # Create Order
        # =====================================================

        with connection.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO orders
                (
                    customer_id,
                    status,
                    total_amount
                )
                VALUES
                (
                    %s,
                    'PLACED',
                    %s
                )
                """,
                (
                    customer_id,
                    total_amount
                )
            )

            order_id = cursor.lastrowid

            # =================================================
            # Insert Order Items
            # =================================================

            for item in validated_items:

                cursor.execute(
                    """
                    INSERT INTO order_items
                    (
                        order_id,
                        product_id,
                        quantity,
                        unit_price
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    """,
                    (
                        order_id,
                        item["product_id"],
                        item["quantity"],
                        item["unit_price"]
                    )
                )

                # =============================================
                # Deduct Inventory
                # =============================================

                cursor.execute(
                    """
                    UPDATE products
                    SET stock_count = stock_count - %s
                    WHERE product_id = %s
                    AND soft_delete IS NULL
                    AND stock_count >= %s
                    """,
                    (
                        item["quantity"],
                        item["product_id"],
                        item["quantity"]
                    )
                )

                if cursor.rowcount != 1:

                    connection.rollback()

                    failed_data = {
                        "order_id": order_id,
                        "customer_id": customer_id,
                        "items": items,
                        "reason": "Inventory deduction failed"
                    }

                    send_failed_order_to_sqs(failed_data)

                    publish_event(
                        "OrderFailed",
                        failed_data
                    )

                    return response(
                        409,
                        "Inventory deduction failed"
                    )

            # =================================================
            # Update Order Status
            # =================================================

            cursor.execute(
                """
                UPDATE orders
                SET status = 'CONFIRMED'
                WHERE order_id = %s
                """,
                (order_id,)
            )

            # =================================================
            # Insert History
            # =================================================

            cursor.execute(
                """
                INSERT INTO history
                (
                    order_id,
                    old_status,
                    new_status,
                    changed_by
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    order_id,
                    "PLACED",
                    "CONFIRMED",
                    "order-processor"
                )
            )

        # =====================================================
        # Commit Transaction
        # =====================================================

        connection.commit()

        # =====================================================
        # OrderConfirmed Event
        # =====================================================

        confirmed_data = {
            "order_id": order_id,
            "customer_id": customer_id,
            "total_amount": total_amount,
            "status": "CONFIRMED"
        }

        publish_event(
            "OrderConfirmed",
            confirmed_data
        )

        print(json.dumps({
            "level": "INFO",
            "message": "Order confirmed successfully",
            "order_id": order_id,
            "customer_id": customer_id,
            "total_amount": total_amount
        }, default=str))

        return response(
            200,
            "Order confirmed successfully",
            {
                "order_id": order_id,
                "status": "CONFIRMED",
                "total_amount": total_amount
            }
        )

    except Exception as e:

        if connection:
            connection.rollback()

        failed_data = {
            "order_id": order_id,
            "customer_id": event.get("customer_id"),
            "items": event.get("items"),
            "reason": str(e)
        }

        print(json.dumps({
            "level": "ERROR",
            "message": "Order processing failed",
            "order_id": order_id,
            "error": str(e)
        }))

        try:
            send_failed_order_to_sqs(failed_data)

            publish_event(
                "OrderFailed",
                failed_data
            )

        except Exception as failure_error:

            print(json.dumps({
                "level": "ERROR",
                "message": "Failed to store failed order",
                "error": str(failure_error)
            }))

        return response(
            500,
            "Order processing failed",
            {
                "order_id": order_id
            }
            if order_id
            else None
        )

    finally:

        if connection:
            connection.close()
