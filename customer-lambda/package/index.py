import json
import os
import boto3
import pymysql

ssm = boto3.client("ssm")

DB_HOST = os.environ["DB_HOST"]
DB_PORT = int(os.environ["DB_PORT"])
DB_NAME = os.environ["DB_NAME"]
DB_USERNAME_PARAMETER = os.environ["DB_USERNAME_PARAMETER"]
DB_PASSWORD_PARAMETER = os.environ["DB_PASSWORD_PARAMETER"]


def get_parameter(name):
    response = ssm.get_parameter(
        Name=name,
        WithDecryption=True
    )
    return response["Parameter"]["Value"]


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

        username = get_parameter(DB_USERNAME_PARAMETER)
        password = get_parameter(DB_PASSWORD_PARAMETER)

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

                cursor.execute(
                    """
                    INSERT INTO customers (name, email)
                    VALUES (%s, %s)
                    """,
                    (name, email)
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
                "email": email
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