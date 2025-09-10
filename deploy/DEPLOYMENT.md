# SpeakCare CDK Deployment

This document explains how to deploy the SpeakCare CDK stack with the simplified deployment process.

## Prerequisites

1. **Virtual Environment**: Activate the Python virtual environment
   ```bash
   source venv/bin/activate
   ```

2. **AWS SSO Login**: Make sure you're logged in with AWS SSO
   ```bash
   aws sso login --profile your-profile-name
   ```

3. **CDK Bootstrap**: Bootstrap CDK in your AWS account (one-time setup)
   ```bash
   cdk bootstrap --profile your-profile-name
   ```

## Deployment

### Basic Usage

Deploy with customer name and environment:

```bash
# Check what would be deployed (dry run)
./run_cdk.sh diff --customer-name <name> --environment [dev|stage|prod] --profile speakcare.dev

# Deploy to dev environment
./run_cdk.sh deploy --customer-name <name> --environment dev --profile speakcare.dev

# Deploy to stage environment  
./run_cdk.sh deploy --customer-name <name> --environment stage --profile speakcare.dev

# Deploy to prod environment
./run_cdk.sh deploy --customer-name <name> --environment prod --profile speakcare.dev
```

### Advanced Usage

```bash
# List all stacks
./run_cdk.sh list --customer-name holyname --environment dev --profile speakcare.dev

# Generate CloudFormation template only (no deployment)
./run_cdk.sh synth --customer-name holyname --environment dev --profile speakcare.dev

# Use different AWS profile
./run_cdk.sh deploy --customer-name holyname --environment dev --profile my-aws-profile
```

### Alternative: Direct Python Script

For custom deployments or advanced use cases:

```bash
# Dry run to see what would be deployed
python3 app.py --customer-name holyname --environment dev --profile speakcare.dev --dry-run

# Get help
python3 app.py --help
```

## What the script does automatically

1. **AWS Session Info**: Gets account ID and region from your AWS SSO session
2. **Certificate Lookup**: Automatically finds the ACM certificate for `*.api.{environment}.speakcare.ai`
3. **Domain Generation**: Builds the customer domain as `{customer}.api.{environment}.speakcare.ai`
4. **Error Handling**: Validates all requirements before deployment

## Environment Variables

The script uses these environment variables (all optional):

- `AWS_PROFILE`: Default AWS profile to use (defaults to "default")

## Required AWS Resources

Make sure these exist in your AWS account:

1. **ACM Certificate**: A wildcard certificate for `*.api.{environment}.speakcare.ai`
2. **Route53 Hosted Zone**: For `{environment}.speakcare.ai` domain

## Troubleshooting

### "No ACM certificate found"
- Make sure the certificate exists in the correct region
- Verify the certificate is in "ISSUED" status
- Check that the domain matches `*.api.{environment}.speakcare.ai`

### "Error getting AWS session info"
- Make sure you're logged in with AWS SSO: `aws sso login --profile your-profile`
- Verify your AWS profile is configured correctly
- Check that your AWS credentials haven't expired

### "CDK bootstrap required"
- Run: `cdk bootstrap --profile your-profile-name`
- This only needs to be done once per AWS account/region
