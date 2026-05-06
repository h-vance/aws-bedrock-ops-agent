import boto3
import json
from botocore.exceptions import ClientError

bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

def get_response(user_input):
    try:
        response = bedrock.converse(
            modelId='amazon.titan-text-express-v1',
            messages=[{"role": "user", "content": [{"text": user_input}]}]
        )
        return response['output']['message']['content']['text']
    except ClientError as error:
        return f"Gracefully caught an API error: {error.response['Error']['Code']}"

def lambda_handler(event, context):
    """
    AWS Lambda handler for the assistant.
    Expects event to have a 'body' with 'text' or be the text itself.
    """
    user_input = event.get('text', "Hello")
    result = get_response(user_input)
    
    return {
        'statusCode': 200,
        'body': json.dumps({'response': result})
    }

if __name__ == "__main__":
    print("Automated Assistant started! Type 'quit' to exit.")
    while True:
        user_input = input("\nYou: ")
        if user_input.lower() == 'quit':
            print("Ending chat...")
            break
        print(f"Assistant: {get_response(user_input)}")
