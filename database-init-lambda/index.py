import os
import pymysql


def lambda_handler(event, context):

    connection = None

    try:
        db_host = os.environ["DB_HOST"]
        db_name = os.environ.get("DB_NAME", "cloudmart")

        db_user = os.environ["DB_USERNAME"]
        db_password = os.environ["DB_PASSWORD"]

        connection = pymysql.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            database=db_name,
            port=3306,
            connect_timeout=10,
            autocommit=False
        )

        cursor = connection.cursor()

        schema_path = os.path.join(
            os.path.dirname(__file__),
            "schema.sql"
        )

        with open(schema_path, "r", encoding="utf-8") as file:
            schema = file.read()

        statements = []

        for statement in schema.split(";"):

            statement = statement.strip()

            if not statement:
                continue

            upper_statement = statement.upper()

            # These are not needed because Lambda already
            # connects directly to the cloudmart database.
            if upper_statement.startswith("CREATE DATABASE"):
                continue

            if upper_statement.startswith("USE CLOUDMART"):
                continue

            if upper_statement.startswith("SHOW TABLES"):
                continue

            # Remove SQL comments
            lines = statement.splitlines()

            lines = [
                line for line in lines
                if not line.strip().startswith("--")
            ]

            statement = "\n".join(lines).strip()

            if statement:
                statements.append(statement)

        for statement in statements:
            print("Executing:", statement[:100])
            cursor.execute(statement)

        connection.commit()

        cursor.execute("SHOW TABLES")

        tables = [
            row[0]
            for row in cursor.fetchall()
        ]

        print("Database initialization successful.")
        print("Tables:", tables)

        return {
            "statusCode": 200,
            "message": "Database initialized successfully",
            "tables": tables
        }

    except Exception as error:

        if connection:
            connection.rollback()

        print("Database initialization failed:", str(error))

        raise

    finally:

        if connection:
            connection.close()