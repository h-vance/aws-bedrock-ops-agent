<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customGradient=ff4d6d,ff8c42,4c1130&height=250&section=header&text=aws-bedrock-agent%20|%20Harrison%20Vance&fontSize=60&animation=fadeIn&fontColor=fff" />
</p>

<p align="center">
  <em>Autonomous AI orchestration layer for automated cloud infrastructure troubleshooting and management.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/AWS-232F3E?style=for-the-badge&logo=amazonaws&logoColor=white" height="28">&nbsp;&nbsp;<img src="https://img.shields.io/badge/Terraform-7B42BC?style=for-the-badge&logo=terraform&logoColor=white" height="28">&nbsp;&nbsp;<img src="https://img.shields.io/badge/Go-00ADD8?style=for-the-badge&logo=go&logoColor=white" height="28">&nbsp;&nbsp;<img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" height="28">&nbsp;&nbsp;<img src="https://img.shields.io/badge/Bash-4EAA25?style=for-the-badge&logo=gnubash&logoColor=white" height="28">
</p>

---


<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=2,5,10&height=120&section=header&text=AWS%20BEDROCK%20AGENT&fontSize=30&animation=fadeIn&fontAlignY=35" width="100%"/>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Case_Study-Autonomous_AI_Infra_Orchestration-BB9AF7?style=for-the-badge&logo=dev.to&logoColor=white" height="35">
</p>

<p align="center">
  <em>Autonomous AI orchestration layer for automated cloud infrastructure troubleshooting and management.</em>
</p>

<br/>
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
