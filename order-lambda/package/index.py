import json
import os
import boto3
import pymysql


lambda_client = boto3.client("lambda")
events_client = boto3.client("events")
ssm_client = boto3.client("ssm")


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


# =====================================================
# RDS CONNECTION
# =====================================================
def get_db_connection():

    host = ssm_client.get_parameter(
        Name="/cloudmart/dev/rds/host",
        WithDecryption=True
    )["Parameter"]["Value"]

    port = ssm_client.get_parameter(
        Name="/cloudmart/dev/rds/port",
        WithDecryption=True
    )["Parameter"]["Value"]

    username = ssm_client.get_parameter(
        Name="/cloudmart/dev/rds/username",
        WithDecryption=True
    )["Parameter"]["Value"]

    password = ssm_client.get_parameter(
        Name="/cloudmart/dev/rds/password",
        WithDecryption=True
    )["Parameter"]["Value"]

    database = ssm_client.get_parameter(
        Name="/cloudmart/dev/rds/db-name",
        WithDecryption=True
    )["Parameter"]["Value"]

    return pymysql.connect(
        host=host,
        port=int(port),
        user=username,
        password=password,
        database=database,
        cursorclass=pymysql.cursors.DictCursor
    )


def lambda_handler(event, context):

    try:
        method = event.get("httpMethod", "")
        path = event.get("path", "")

        # =====================================================
        # POST /orders
        # =====================================================
        if method == "POST" and path.rstrip("/") == "/orders":

            body = json.loads(event.get("body") or "{}")

            customer_id = body.get("customer_id")
            items = body.get("items")

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

            for item in items:

                if not item.get("product_id"):
                    return response(
                        400,
                        "product_id is required for every item"
                    )

                if not item.get("quantity") or int(item.get("quantity")) <= 0:
                    return response(
                        400,
                        "quantity must be greater than 0"
                    )

            order_processor_function = os.environ[
                "ORDER_PROCESSOR_FUNCTION"
            ]

            processor_payload = {
                "action": "PROCESS_ORDER",
                "customer_id": customer_id,
                "items": items
            }

            invoke_response = lambda_client.invoke(
                FunctionName=order_processor_function,
                InvocationType="RequestResponse",
                Payload=json.dumps(processor_payload)
            )

            processor_payload_response = (
                invoke_response["Payload"].read()
            )

            processor_result = json.loads(
                processor_payload_response
            )

            if isinstance(processor_result.get("body"), str):
                processor_body = json.loads(processor_result["body"])
            else:
                processor_body = processor_result

            # Handle Lambda-level failure
            if invoke_response.get("FunctionError"):
                print(json.dumps({
                    "level": "ERROR",
                    "message": "Order Processor Lambda failed",
                    "processor_result": processor_result
                }))

                return response(
                    500,
                    "Order processing failed"
                )

            # Handle application-level failure
            if processor_result.get("statusCode", 200) >= 400:

                return response(
                    processor_result.get("statusCode", 500),
                    processor_body.get(
                        "message",
                        "Order processing failed"
                    ),
                    {
                        "order_id": processor_body.get("order_id")
                    }
                    if processor_body.get("order_id")
                    else None
                )

            order_id = processor_body.get("order_id")

            # =================================================
            # OrderPlaced Event
            # =================================================
            try:

                events_client.put_events(
                    Entries=[
                        {
                            "Source": "cloudmart.order",
                            "DetailType": "OrderPlaced",
                            "Detail": json.dumps({
                                "order_id": order_id,
                                "customer_id": customer_id
                            }),
                            "EventBusName": os.environ[
                                "EVENT_BUS_NAME"
                            ]
                        }
                    ]
                )

            except Exception as event_error:

                print(json.dumps({
                    "level": "ERROR",
                    "message": "Failed to publish OrderPlaced event",
                    "error": str(event_error),
                    "order_id": order_id
                }))

            return response(
                201,
                "Order placed successfully",
                {
                    "order_id": order_id
                }
            )
        # =====================================================
        # PATCH /orders/{order_id}
        # =====================================================
        elif method == "PATCH":

            path_parameters = event.get("pathParameters") or {}

            path_parameter_id = (
                path_parameters.get("order_id")
                or path_parameters.get("id")
            )

            if path_parameter_id:
                try:
                   order_id = int(path_parameter_id)
                except (ValueError, TypeError):
                    return response(
                400,
                "Invalid order ID"
            )

        # existing SELECT for one order goes here

            body = json.loads(event.get("body") or "{}")
            new_status = body.get("status")

            if new_status != "CANCELLED":
                return response(
                    400,
                    "Only status CANCELLED is supported"
                )

            conn = get_db_connection()
            cursor = conn.cursor()

            try:
                cursor.execute("""
                    SELECT order_id, customer_id, status
                    FROM orders
                    WHERE order_id = %s
                    FOR UPDATE
                """, (order_id,))

                order = cursor.fetchone()

                if not order:
                    return response(
                        404,
                        "Order not found"
                    )

                current_status = order["status"]

                if current_status not in ("PLACED", "CONFIRMED"):
                    return response(
                        400,
                        f"Order cannot be cancelled from status {current_status}"
                    )

                cursor.execute("""
                    SELECT product_id, quantity
                    FROM order_items
                    WHERE order_id = %s
                """, (order_id,))

                items = cursor.fetchall()

                for item in items:
                    cursor.execute("""
                        UPDATE products
                        SET stock_count = stock_count + %s
                        WHERE product_id = %s
                          AND soft_delete IS NULL
                    """, (
                        item["quantity"],
                        item["product_id"]
                    ))

                cursor.execute("""
                    UPDATE orders
                    SET status = 'CANCELLED'
                    WHERE order_id = %s
                """, (order_id,))

                cursor.execute("""
                    INSERT INTO history (
                        order_id,
                        old_status,
                        new_status,
                        changed_by
                    )
                    VALUES (%s, %s, 'CANCELLED', %s)
                """, (
                    order_id,
                    current_status,
                    "customer"
                ))

                conn.commit()

                return response(
                    200,
                    "Order cancelled successfully",
                    {
                        "order_id": order_id,
                        "status": "CANCELLED"
                    }
                )

            except Exception:
                conn.rollback()
                raises

            finally:
                cursor.close()
                conn.close()
        # =====================================================
        # GET /orders OR GET /orders/{id}
        # =====================================================
        elif method == "GET":

            path_parameter_id = (
                event.get("pathParameters") or {}
            ).get("order_id")

            conn = get_db_connection()
            cursor = conn.cursor()

            try:

                # =================================================
                # GET /orders/{id}
                # =================================================
                if path_parameter_id:

                    try:
                        order_id = int(path_parameter_id)
                    except ValueError:
                        return response(
                            400,
                            "Invalid order ID"
                        )

                    cursor.execute("""
                        SELECT
                            order_id,
                            customer_id,
                            status,
                            total_amount,
                            created_at,
                            updated_at
                        FROM orders
                        WHERE order_id = %s
                    """, (order_id,))

                    order = cursor.fetchone()

                    if not order:
                        return response(
                            404,
                            "Order not found"
                        )

                    cursor.execute("""
                        SELECT
                            oi.order_item_id,
                            oi.product_id,
                            p.name AS product_name,
                            oi.quantity,
                            oi.unit_price
                        FROM order_items oi
                        JOIN products p
                            ON oi.product_id = p.product_id
                        WHERE oi.order_id = %s
                    """, (order_id,))

                    order_items = cursor.fetchall()

                    order["items"] = order_items

                    return response(
                        200,
                        "Order retrieved successfully",
                        {
                            "order": order
                        }
                    )

                # =================================================
                # GET /orders
                # =================================================
                else:

                    query_parameters = (
                        event.get("queryStringParameters") or {}
                    )

                    customer_id = query_parameters.get(
                        "customerId"
                    )

                    if customer_id:

                        try:
                            customer_id = int(customer_id)
                        except ValueError:
                            return response(
                                400,
                                "Invalid customerId"
                            )

                        cursor.execute("""
                            SELECT
                                order_id,
                                customer_id,
                                status,
                                total_amount,
                                created_at,
                                updated_at
                            FROM orders
                            WHERE customer_id = %s
                            ORDER BY created_at DESC
                        """, (customer_id,))

                    else:

                        cursor.execute("""
                            SELECT
                                order_id,
                                customer_id,
                                status,
                                total_amount,
                                created_at,
                                updated_at
                            FROM orders
                            ORDER BY created_at DESC
                        """)

                    orders = cursor.fetchall()

                    return response(
                        200,
                        "Orders retrieved successfully",
                        {
                            "orders": orders
                        }
                    )

            finally:
                cursor.close()
                conn.close()

        # =====================================================
        # Unsupported Method
        # =====================================================

        return response(
            405,
            "Method not supported"
        )

    except json.JSONDecodeError:

        return response(
            400,
            "Invalid JSON request body"
        )

    except Exception as e:

        print(json.dumps({
            "level": "ERROR",
            "message": "Order Lambda error",
            "error": str(e),
            "method": event.get("httpMethod"),
            "path": event.get("path")
        }))

        return response(
            500,
            "Internal server error"
        )