#!/usr/bin/env python3
"""
CDK App for SpeakCare - Reads values from CDK context
This is what CDK will run directly
"""
import aws_cdk
from cdk.customer_stack import SpeakCareCustomerStack
from get_cert import get_acm_cert_arn_by_wildcard

app = aws_cdk.App()

# Get values from CDK context (passed via --context arguments)
customer_name = app.node.try_get_context("customer_name")
environment = app.node.try_get_context("environment")
account = app.node.try_get_context("account")
region = app.node.try_get_context("region")
aws_profile = app.node.try_get_context("aws_profile")
version = app.node.try_get_context("version") or "v1"  # Default to v1
space = app.node.try_get_context("space") or "tenants"  # Default to tenants

# Validate required context values
if not all([customer_name, environment, account, region]):
    raise ValueError("Missing required CDK context values. Use run_cdk.sh script.")

# Build domain names
api_domain = f"api.{environment}.speakcare.ai"
customer_domain = f"{customer_name}.{api_domain}"
wildcard_domain = f"*.{api_domain}"

# Get ACM certificate ARN using the existing function
acm_cert_arn = get_acm_cert_arn_by_wildcard(wildcard_domain, aws_profile)
if not acm_cert_arn:
    raise ValueError(f"No ACM certificate found for domain '{wildcard_domain}'")

# Create the stack
SpeakCareCustomerStack(
    app,
    f"SpeakCareCustomer-{customer_name}-{environment}",
    customer_name=customer_name,
    environment=environment,
    acm_cert_arn=acm_cert_arn,
    customer_domain=customer_domain,
    aws_profile=aws_profile,
    version=version,
    space=space,
    env=aws_cdk.Environment(
        account=account,
        region=region,
    ),
)

app.synth()
