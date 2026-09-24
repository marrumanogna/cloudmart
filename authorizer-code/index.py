import os
import pymysql

DB_HOST = os.environ["DB_HOST"]
DB_PORT = int(os.environ["DB_PORT"])
DB_NAME = os.environ["DB_NAME"]


def get_customer_by_token(customer_token):
    username = os.environ["DB_USERNAME"]
    password = os.environ["DB_PASSWORD"]
    admin_token = os.environ["ADMIN_TOKEN"]

    connection = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=username,
        password=password,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5
    )

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT customer_id
                FROM customers
                WHERE customer_token = %s
                LIMIT 1
                """,
                (customer_token,)
            )

            return cursor.fetchone()

    finally:
        connection.close()


def generate_policy(principal_id, effect, resource, role=None, customer_id=None):
    response = {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": effect,
                    "Resource": resource
                }
            ]
        }
    }

    context = {}

    if role:
        context["role"] = role

    if customer_id is not None:
        context["customer_id"] = str(customer_id)

    if context:
        response["context"] = context

    return response


def lambda_handler(event, context):

    method_arn = event.get("methodArn", "*")
    print(f"Method ARN: {method_arn}")

    arn_parts = method_arn.split("/")

    if len(arn_parts) >= 2:
        policy_resource = f"{arn_parts[0]}/{arn_parts[1]}/*"
    else:
        policy_resource = method_arn

    provided_token = event.get("authorizationToken", "")

    if not provided_token:
        headers = event.get("headers") or {}
        provided_token = headers.get("authorization", "")

    if not provided_token:
        headers = event.get("headers") or {}
        provided_token = headers.get("Authorization", "")

    if provided_token.lower().startswith("bearer "):
        provided_token = provided_token[7:].strip()

    try:
        admin_token = ADMIN_TOKEN

        if provided_token == admin_token:
            print("Admin authenticated")

            return generate_policy(
                "cloudmart-admin",
                "Allow",
                policy_resource,
                "ADMIN"
            )

        customer = get_customer_by_token(provided_token)

        if customer:
            customer_id = customer["customer_id"]

            print(
                f"Customer authenticated: customer_id={customer_id}"
            )

            # Get the HTTP method and path from the API Gateway method ARN
            if len(arn_parts) >= 4:
                request_method = arn_parts[2]
                request_path = "/" + "/".join(arn_parts[3:])
            else:
                request_method = ""
                request_path = ""

            # Customers cannot create, update, or delete products
            request_method = event.get("httpMethod", request_method)
            request_path = event.get("path", request_path)

            if (
                (request_path.rstrip("/") == "/products"
                 and request_method == "POST")
                or
                (request_path.startswith("/products/")
                 and request_method in ["PUT", "DELETE"])
            ):
                print("Customer is not authorized for product modification")

                return generate_policy(
                    f"cloudmart-customer-{customer_id}",
                    "Deny",
                    method_arn,
                    "CUSTOMER",
                    customer_id
                )

            return generate_policy(
                f"cloudmart-customer-{customer_id}",
                "Allow",
                method_arn,
                "CUSTOMER",
                customer_id
            )

    except Exception as error:
        print(f"Authorization lookup failed: {error}")

        return generate_policy(
            "cloudmart-unauthorized",
            "Deny",
            method_arn
        )

    print("Authorization failed")
    raise Exception("Unauthorized")