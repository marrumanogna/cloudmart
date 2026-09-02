import json
import os
import boto3


lambda_client = boto3.client("lambda")
events_client = boto3.client("events")


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
                    processor_result.get(
                        "message",
                        "Order processing failed"
                    ),
                    {
                        "order_id": processor_result.get("order_id")
                    }
                    if processor_result.get("order_id")
                    else None
                )

            order_id = processor_result.get("order_id")

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