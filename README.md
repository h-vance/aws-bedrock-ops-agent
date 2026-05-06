<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=rect&color=09090b&height=200&section=header&text=HARRISON%20VANCE&fontSize=70&fontAlignY=40&animation=fadeIn&fontColor=10b981&desc=INFRASTRUCTURE%20ENGINEERING%20&%20SYSTEMS%20ARCHITECTURE&descSize=20&descAlignY=65&descAlign=50" />
</p>

<p align="center">
  <code>[ STATUS: ACTIVE ]</code> &nbsp;&nbsp; <code>[ LOCATION: APAC/REMOTE ]</code> &nbsp;&nbsp; <code>[ SYNCED: 2026.05.03 ]</code>
</p>

<h1 align='center'>Aws Bedrock Agent</h1>

<p align="center">
  <em>Autonomous AI orchestration layer for automated cloud infrastructure troubleshooting and management.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/AWS-18181b?style=for-the-badge&logo=amazon&logoColor=10b981" height="28">&nbsp;&nbsp;<img src="https://img.shields.io/badge/Terraform-18181b?style=for-the-badge&logo=terraform&logoColor=10b981" height="28">&nbsp;&nbsp;<img src="https://img.shields.io/badge/Go-18181b?style=for-the-badge&logo=go&logoColor=10b981" height="28">&nbsp;&nbsp;<img src="https://img.shields.io/badge/Python-18181b?style=for-the-badge&logo=python&logoColor=10b981" height="28">&nbsp;&nbsp;<img src="https://img.shields.io/badge/Bash-18181b?style=for-the-badge&logo=gnubash&logoColor=10b981" height="28">
</p>

---



















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
