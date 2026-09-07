import json
import os
import boto3
import pymysql


ssm = boto3.client("ssm")
sqs = boto3.client("sqs")
events_client = boto3.client("events")


def get_db_connection():
    print("DEBUG: Starting get_db_connection")

    print("DEBUG: Getting DB username from SSM")
    username = ssm.get_parameter(
        Name=os.environ["DB_USERNAME_PARAMETER"],
        WithDecryption=True
    )["Parameter"]["Value"]

    print("DEBUG: Getting DB password from SSM")
    password = ssm.get_parameter(
        Name=os.environ["DB_PASSWORD_PARAMETER"],
        WithDecryption=True
    )["Parameter"]["Value"]

    print("DEBUG: Connecting to RDS")

    connection = pymysql.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ["DB_PORT"]),
        user=username,
        password=password,
        database=os.environ["DB_NAME"],
        connect_timeout=10,
        cursorclass=pymysql.cursors.DictCursor
    )

    print("DEBUG: Connected to RDS successfully")

    return connection


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
        print(f"DEBUG: Publishing EventBridge event: {detail_type}")

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

        print(f"DEBUG: EventBridge event published: {detail_type}")

    except Exception as e:
        print(json.dumps({
            "level": "ERROR",
            "message": "EventBridge publish failed",
            "event_type": detail_type,
            "error": str(e)
        }))


def send_failed_order_to_sqs(order_data):
    print("DEBUG: Sending failed order to SQS")

    sqs.send_message(
        QueueUrl=os.environ["FAILED_ORDERS_QUEUE_URL"],
        MessageBody=json.dumps(order_data, default=str)
    )

    print("DEBUG: Failed order sent to SQS")


def lambda_handler(event, context):

    connection = None
    order_id = None

    try:

        message = event

        print(json.dumps({
            "DEBUG_MESSAGE": message,
            "DEBUG_MESSAGE_TYPE": str(type(message))
        }))

        print("DEBUG: Validating processor action")

        if message.get("action") != "PROCESS_ORDER":
            return response(
                400,
                "Invalid order processor action"
            )

        customer_id = message.get("customer_id")
        items = message.get("items")

        print(f"DEBUG: customer_id = {customer_id}")
        print(f"DEBUG: items = {items}")

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

        print("DEBUG: Connecting to database")

        connection = get_db_connection()

        print("DEBUG: Database connection established")

        # =====================================================
        # Validate Customer
        # =====================================================

        print("DEBUG: Starting customer validation")

        with connection.cursor() as cursor:

            print("DEBUG: Executing customer query")

            cursor.execute(
                """
                SELECT customer_id
                FROM customers
                WHERE customer_id = %s
                """,
                (customer_id,)
            )

            print("DEBUG: Customer query completed")

            customer = cursor.fetchone()

            print(f"DEBUG: Customer result = {customer}")

        if not customer:

            print("DEBUG: Customer not found")

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

        print("DEBUG: Customer validation successful")

        # =====================================================
        # Validate Products and Stock
        # =====================================================

        total_amount = 0
        validated_items = []

        print("DEBUG: Starting product and stock validation")

        with connection.cursor() as cursor:

            for item in items:

                product_id = item.get("product_id")
                quantity = int(item.get("quantity", 0))

                print(
                    f"DEBUG: Processing product_id={product_id}, "
                    f"quantity={quantity}"
                )

                if not product_id or quantity <= 0:

                    print("DEBUG: Invalid product_id or quantity")

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

                print(
                    f"DEBUG: Executing FOR UPDATE product query "
                    f"for product_id={product_id}"
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

                print(
                    f"DEBUG: FOR UPDATE query completed "
                    f"for product_id={product_id}"
                )

                product = cursor.fetchone()

                print(
                    f"DEBUG: Product result for product_id={product_id}: "
                    f"{product}"
                )

                if not product:

                    print(
                        f"DEBUG: Product not found "
                        f"for product_id={product_id}"
                    )

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

                print(
                    f"DEBUG: Available stock for product_id={product_id}: "
                    f"{product['stock_count']}"
                )

                if product["stock_count"] < quantity:

                    print(
                        f"DEBUG: Insufficient stock "
                        f"for product_id={product_id}"
                    )

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

                print(
                    f"DEBUG: Item total for product_id={product_id}: "
                    f"{item_total}"
                )

                validated_items.append({
                    "product_id": product_id,
                    "quantity": quantity,
                    "unit_price": product["price"]
                })

                print(
                    f"DEBUG: Product validation completed "
                    f"for product_id={product_id}"
                )

        print("DEBUG: Product and stock validation completed")
        print(f"DEBUG: Total amount = {total_amount}")

        # =====================================================
        # Create Order
        # =====================================================

        print("DEBUG: Starting order creation")

        with connection.cursor() as cursor:

            print("DEBUG: Inserting order")

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

            print("DEBUG: Order INSERT completed")

            order_id = cursor.lastrowid

            print(f"DEBUG: New order_id = {order_id}")

            # =================================================
            # Insert Order Items
            # =================================================

            for item in validated_items:

                print(
                    f"DEBUG: Inserting order item "
                    f"for product_id={item['product_id']}"
                )

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

                print(
                    f"DEBUG: Order item INSERT completed "
                    f"for product_id={item['product_id']}"
                )

                # =============================================
                # Deduct Inventory
                # =============================================

                print(
                    f"DEBUG: Updating inventory "
                    f"for product_id={item['product_id']}"
                )

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

                print(
                    f"DEBUG: Inventory UPDATE completed "
                    f"for product_id={item['product_id']}, "
                    f"rowcount={cursor.rowcount}"
                )

                if cursor.rowcount != 1:

                    print("DEBUG: Inventory deduction failed")

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

            print(
                f"DEBUG: Updating order status to CONFIRMED "
                f"for order_id={order_id}"
            )

            cursor.execute(
                """
                UPDATE orders
                SET status = 'CONFIRMED'
                WHERE order_id = %s
                """,
                (order_id,)
            )

            print("DEBUG: Order status UPDATE completed")

            # =================================================
            # Insert History
            # =================================================

            print(
                f"DEBUG: Inserting history "
                f"for order_id={order_id}"
            )

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

            print("DEBUG: History INSERT completed")

        # =====================================================
        # Commit Transaction
        # =====================================================

        print(f"DEBUG: Starting database COMMIT for order_id={order_id}")

        connection.commit()

        print(f"DEBUG: Database COMMIT completed for order_id={order_id}")

        # =====================================================
        # OrderConfirmed Event
        # =====================================================

        confirmed_data = {
            "order_id": order_id,
            "customer_id": customer_id,
            "total_amount": total_amount,
            "status": "CONFIRMED"
        }

        print("DEBUG: Preparing OrderConfirmed event")

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

        print("DEBUG: Exception occurred in Order Processor")

        if connection:
            print("DEBUG: Rolling back database transaction")
            connection.rollback()
            print("DEBUG: Database rollback completed")

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

            print("DEBUG: Sending failed order to SQS")

            send_failed_order_to_sqs(failed_data)

            print("DEBUG: Publishing OrderFailed event")

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

        print("DEBUG: Entering finally block")

        if connection:
            print("DEBUG: Closing database connection")
            connection.close()
            print("DEBUG: Database connection closed")

