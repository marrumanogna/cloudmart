import boto3
import os

ssm = boto3.client("ssm")

PARAMETER_NAME = os.environ["AUTH_TOKEN_PARAMETER"]


def get_auth_token():
    response = ssm.get_parameter(
        Name=PARAMETER_NAME,
        WithDecryption=True
    )
    return response["Parameter"]["Value"]


def generate_policy(principal_id, effect, resource):
    return {
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


def lambda_handler(event, context):

    method_arn = event.get("methodArn", "*")
    provided_token = event.get("authorizationToken", "")

    if not provided_token:
        headers = event.get("headers") or {}
        provided_token = headers.get("authorization", "")

    if provided_token.lower().startswith("bearer "):
        provided_token = provided_token[7:].strip()

    try:
        expected_token = get_auth_token()

    except Exception as error:
        print(f"Failed to retrieve authentication token: {error}")

        return generate_policy(
            "cloudmart-unauthorized",
            "Deny",
            method_arn
        )

    if provided_token and provided_token == expected_token:
        print("Authorization successful")

        return generate_policy(
            "cloudmart-user",
            "Allow",
            method_arn
        )

    print("Authorization failed")

    raise Exception("Unauthorized")