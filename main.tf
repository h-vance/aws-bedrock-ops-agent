provider "aws" {
  region = "us-east-1"
}

resource "aws_iam_role" "lambda_role" {
  name = "bedrock_agent_role"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Action = "sts:AssumeRole", Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" } }]
  })
}

resource "aws_iam_role_policy" "bedrock_policy" {
  name = "bedrock_access"
  role = aws_iam_role.lambda_role.id
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Action = "bedrock:InvokeModel", Effect = "Allow", Resource = "*" }]
  })
}

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "assistant.py"
  output_path = "assistant.zip"
}

resource "aws_lambda_function" "bedrock_agent" {
  filename         = "assistant.zip"
  function_name    = "BedrockAgent"
  role             = aws_iam_role.lambda_role.arn
  handler          = "assistant.lambda_handler"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime          = "python3.12"
  timeout          = 30
}
