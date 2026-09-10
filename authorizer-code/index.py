import boto3
import os

ssm = boto3.client("ssm")

CUSTOMER_TOKEN_PARAMETER = os.environ["CUSTOMER_TOKEN_PARAMETER"]
ADMIN_TOKEN_PARAMETER = os.environ["ADMIN_TOKEN_PARAMETER"]


def get_token(parameter_name):
    response = ssm.get_parameter(
        Name=parameter_name,
        WithDecryption=True
    )
    return response["Parameter"]["Value"]


def generate_policy(principal_id, effect, resource, role=None):
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

    if role:
        response["context"] = {
            "role": role
        }

    return response


def lambda_handler(event, context):

    method_arn = event.get("methodArn", "*")

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
        customer_token = get_token(CUSTOMER_TOKEN_PARAMETER)
        admin_token = get_token(ADMIN_TOKEN_PARAMETER)

    except Exception as error:
        print(f"Failed to retrieve authentication tokens: {error}")

        return generate_policy(
            "cloudmart-unauthorized",
            "Deny",
            method_arn
        )

    if provided_token == customer_token:
        print("Customer authenticated")

        return generate_policy(
            "cloudmart-customer",
            "Allow",
            policy_resource,
            "CUSTOMER"
        )

    if provided_token == admin_token:
        print("Admin authenticated")

        return generate_policy(
            "cloudmart-admin",
            "Allow",
            policy_resource,
            "ADMIN"
        )

    print("Authorization failed")
    raise Exception("Unauthorized")