import json
import os

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "amazon.titan-text-express-v1")


def _bedrock_client():
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError("boto3 is required for Lambda Bedrock calls") from exc

    return boto3.client("bedrock-runtime", region_name=AWS_REGION)


def lambda_handler(event, context):
    user_input = event.get("text", "Hello")
    try:
        response = _bedrock_client().converse(
            modelId=BEDROCK_MODEL_ID,
            messages=[{"role": "user", "content": [{"text": user_input}]}],
        )
        result = response["output"]["message"]["content"][0]["text"]
    except Exception as error:
        result = f"Gracefully caught a Bedrock error: {error}"

    return {"statusCode": 200, "body": json.dumps({"response": result})}
