import csv
import io
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import boto3
import pymysql
from botocore.config import Config

aws_config = Config(
    connect_timeout=5,
    read_timeout=5,
    retries={"max_attempts": 1}
)

s3 = boto3.client("s3", config=aws_config)

# ------------------------------------------------------------
# DATABASE CONNECTION
# ------------------------------------------------------------

def get_db_connection():

    print("REPORT: Getting DB username from environment")

    username = os.environ["DB_USERNAME"]

    print("REPORT: Getting DB password from environment")

    password = os.environ["DB_PASSWORD"]

    print("REPORT: Connecting to RDS")

    connection = pymysql.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ["DB_PORT"]),
        user=username,
        password=password,
        database=os.environ["DB_NAME"],
        connect_timeout=5,
        read_timeout=5,
        write_timeout=5,
        cursorclass=pymysql.cursors.DictCursor
    )

    print("REPORT: Connected to RDS successfully")

    return connection

# ------------------------------------------------------------
# LAMBDA HANDLER
# ------------------------------------------------------------

def lambda_handler(event, context):

    connection = None

    try:

        # Use India time so "today" matches the dashboard/report date.
        report_date = datetime.now(
            ZoneInfo("Asia/Kolkata")
        ).date()

        print(json.dumps({
            "level": "INFO",
            "message": "Starting daily report generation",
            "report_date": str(report_date)
        }))

        # ----------------------------------------------------
        # DATABASE CONNECTION
        # ----------------------------------------------------

        connection = get_db_connection()

        print("REPORT: Database connection established")

        # ----------------------------------------------------
        # QUERY ORDERS
        # ----------------------------------------------------

        print(
            f"REPORT: Fetching orders for {report_date}"
        )

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    o.order_id,
                    o.customer_id,
                    c.name AS customer_name,
                    o.status,
                    o.total_amount,
                    o.created_at,
                    COUNT(oi.order_item_id) AS item_count,
                    COALESCE(SUM(oi.quantity), 0) AS total_quantity
                FROM orders o
                LEFT JOIN customers c
                    ON c.customer_id = o.customer_id
                LEFT JOIN order_items oi
                    ON oi.order_id = o.order_id
                WHERE DATE(o.created_at) = %s
                GROUP BY
                    o.order_id,
                    o.customer_id,
                    c.name,
                    o.status,
                    o.total_amount,
                    o.created_at
                ORDER BY o.created_at DESC
                """,
                (report_date,)
            )

            rows = cursor.fetchall()

        print(
            f"REPORT: Database query completed. "
            f"Rows returned: {len(rows)}"
        )

        # ----------------------------------------------------
        # CREATE CSV
        # ----------------------------------------------------

        print("REPORT: Creating CSV in memory")

        csv_buffer = io.StringIO()

        fieldnames = [
            "order_id",
            "customer_id",
            "customer_name",
            "status",
            "total_amount",
            "created_at",
            "item_count",
            "total_quantity"
        ]

        writer = csv.DictWriter(
            csv_buffer,
            fieldnames=fieldnames
        )

        writer.writeheader()

        for row in rows:

            writer.writerow({
                "order_id": row["order_id"],
                "customer_id": row["customer_id"],
                "customer_name": row["customer_name"],
                "status": row["status"],
                "total_amount": row["total_amount"],
                "created_at": row["created_at"],
                "item_count": row["item_count"],
                "total_quantity": row["total_quantity"]
            })

        print("REPORT: CSV created successfully")

        # ----------------------------------------------------
        # UPLOAD CSV TO S3
        # ----------------------------------------------------

        bucket = os.environ["REPORTS_BUCKET"]

        key = (
            f"reports/daily_report_"
            f"{report_date.isoformat()}.csv"
        )

        print(
            f"REPORT: Uploading CSV to S3. "
            f"Bucket={bucket}, Key={key}"
        )

        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=csv_buffer.getvalue().encode("utf-8"),
            ContentType="text/csv"
        )

        print("REPORT: CSV uploaded to S3 successfully")

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        print(json.dumps({
            "level": "INFO",
            "message": "Daily report generated successfully",
            "bucket": bucket,
            "key": key,
            "row_count": len(rows)
        }))

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Daily report generated successfully",
                "report_date": str(report_date),
                "bucket": bucket,
                "key": key,
                "row_count": len(rows)
            })
        }

    except Exception as error:

        print(json.dumps({
            "level": "ERROR",
            "message": "Daily report generation failed",
            "error": str(error)
        }))

        raise

    finally:

        if connection:

            print("REPORT: Closing database connection")

            connection.close()

