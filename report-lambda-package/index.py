import csv
import io
import json
import os
from datetime import datetime, timezone

import boto3
import pymysql


ssm = boto3.client("ssm")
s3 = boto3.client("s3")


def get_parameter(name):
    response = ssm.get_parameter(
        Name=name,
        WithDecryption=True
    )
    return response["Parameter"]["Value"]


def get_db_connection():
    return pymysql.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "3306")),
        user=get_parameter(os.environ["DB_USERNAME_PARAMETER"]),
        password=get_parameter(os.environ["DB_PASSWORD_PARAMETER"]),
        database=os.environ["DB_NAME"],
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10
    )


def lambda_handler(event, context):

    connection = None

    try:
        connection = get_db_connection()

        with connection.cursor() as cursor:

            cursor.execute("""
                SELECT
                    o.order_id,
                    o.customer_id,
                    o.total_amount,
                    o.status,
                    o.created_at
                FROM orders o
                ORDER BY o.created_at DESC
            """)

            orders = cursor.fetchall()

        output = io.StringIO()

        writer = csv.writer(output)

        writer.writerow([
            "order_id",
            "customer_id",
            "total_amount",
            "status",
            "created_at"
        ])

        for order in orders:
            writer.writerow([
                order["order_id"],
                order["customer_id"],
                order["total_amount"],
                order["status"],
                order["created_at"]
            ])

        csv_content = output.getvalue()

        timestamp = datetime.now(timezone.utc).strftime(
            "%Y-%m-%d-%H-%M-%S"
        )

        key = f"reports/daily-report-{timestamp}.csv"

        s3.put_object(
            Bucket=os.environ["REPORTS_BUCKET"],
            Key=key,
            Body=csv_content.encode("utf-8"),
            ContentType="text/csv"
        )

        result = {
            "message": "Daily report generated successfully",
            "bucket": os.environ["REPORTS_BUCKET"],
            "key": key,
            "order_count": len(orders)
        }

        print(json.dumps(result))

        return {
            "statusCode": 200,
            "body": json.dumps(result)
        }

    except Exception as e:

        print(json.dumps({
            "message": "Report generation failed",
            "error": str(e)
        }))

        raise

    finally:

        if connection:
            connection.close()