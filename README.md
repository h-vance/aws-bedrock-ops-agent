# AWS Bedrock Agent

A robust infrastructure and application framework for deploying automated assistants using Amazon Bedrock. This repository provides the Terraform configurations for AWS Lambda integration and a Python-based execution logic for interacting with large language models.

[![AWS](https://img.shields.io/badge/AWS-%23FF9900.svg?style=for-the-badge&logo=amazon-aws&logoColor=white)](https://aws.amazon.com/)
[![Terraform](https://img.shields.io/badge/terraform-%235835CC.svg?style=for-the-badge&logo=terraform&logoColor=white)](https://www.terraform.io/)
[![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)](https://www.python.org/)
[![Boto3](https://img.shields.io/badge/Boto3-orange?style=for-the-badge)](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
[![GitHub Actions](https://img.shields.io/badge/github%20actions-%232671E5.svg?style=for-the-badge&logo=githubactions&logoColor=white)](https://github.com/features/actions)

## Features

- **Infrastructure as Code**: Full Terraform deployment for IAM roles, Lambda functions, and policy management.
- **Serverless Execution**: Optimized Python 3.12 runtime for AWS Lambda.
- **Model Integration**: Direct interface with Amazon Bedrock using the Boto3 SDK.
- **Dual-Mode Operation**: Supports both serverless Lambda execution and local command-line interface testing.

## Repository Structure

- `assistant.py`: Core logic for model interaction and handler for AWS Lambda.
- `main.tf`: Terraform configuration for AWS resource provisioning.
- `.gitignore`: Standard exclusions for Python and Terraform environments.

## Deployment

### Prerequisites

- AWS CLI configured with appropriate credentials.
- Terraform installed locally.
- Python 3.12 environment.

### Infrastructure Provisioning

1. Initialize Terraform:
   ```bash
   terraform init
   ```

2. Review the plan:
   ```bash
   terraform plan
   ```

3. Deploy the resources:
   ```bash
   terraform apply
   ```

## Local Testing

The assistant can be tested locally using the Python CLI:

```bash
python assistant.py
```

## Security

This project follows the Principle of Least Privilege (PoLP) by restricting IAM roles to specific Bedrock invocation actions. Ensure that the `bedrock_agent_role` is monitored and audited regularly within your AWS environment.

## License

MIT License. See LICENSE for details.
