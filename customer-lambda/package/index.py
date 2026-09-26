import json
import os
import uuid
import pymysql
import hashlib

DB_HOST = os.environ["DB_HOST"]
DB_PORT = int(os.environ["DB_PORT"])
DB_NAME = os.environ["DB_NAME"]


def lambda_handler(event, context):

    try:
        body = json.loads(event.get("body") or "{}")

        name = body.get("name")
        email = body.get("email")

        if not name or not email:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "message": "name and email are required"
                })
            }

        username = os.environ["DB_USERNAME"]
        password = os.environ["DB_PASSWORD"]

        connection = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=username,
            password=password,
            database=DB_NAME,
            cursorclass=pymysql.cursors.DictCursor
        )

        try:
            with connection.cursor() as cursor:

                customer_token = str(uuid.uuid4())

                customer_token_hash = hashlib.sha256(
                    customer_token.encode("utf-8")
                ).hexdigest()

                cursor.execute(
                    """
                    INSERT INTO customers (name, email, customer_token)
                    VALUES (%s, %s, %s)
                    """,
                    (name, email, customer_token_hash)
                )

                customer_id = cursor.lastrowid

            connection.commit()

        finally:
            connection.close()

        return {
            "statusCode": 201,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "message": "Customer created successfully",
                "customer_id": customer_id,
                "name": name,
                "email": email,
                "customer_token": customer_token
            })
        }

    except pymysql.err.IntegrityError:
        return {
            "statusCode": 409,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "message": "Customer email already exists"
            })
        }

    except Exception as error:
        print(f"Customer creation failed: {error}")

        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "message": "Internal server error"
            })
        }