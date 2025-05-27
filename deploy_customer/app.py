#!/usr/bin/env python3
import os
import boto3

import aws_cdk

# from cdk.cdk_stack import CdkStack
from cdk.customer_stack import SpeakCareCustomerStack
from cdk.cdk_stack import CdkStack
from get_cert import get_acm_cert_arn_by_wildcard
# ...rest of your deployment logic



app = aws_cdk.App()

# Get params from env or context
customer_name = app.node.try_get_context("customer_name") or os.environ.get("CUSTOMER_NAME")
environment = app.node.try_get_context("environment") or os.environ.get("SPEAKCARE_ENV", "dev")
acm_cert_arn = app.node.try_get_context("acm_cert_arn") or os.environ.get("ACM_CERT_ARN")
account = app.node.try_get_context("account") or os.environ.get("CDK_DEFAULT_ACCOUNT")
region = app.node.try_get_context("region") or os.environ.get("CDK_DEFAULT_REGION")
api_domain = f"api.{environment}.speakcare.ai"
customer_domain = f"{customer_name}.{api_domain}"
print(f"Customer domain: {customer_domain}")
print(f"ACM cert ARN: {acm_cert_arn}")



if customer_name and environment and acm_cert_arn and account and region:
    SpeakCareCustomerStack(
        app,
        f"SpeakCareCustomer-{customer_name}-{environment}",
        customer_name=customer_name,
        environment=environment,
        acm_cert_arn=acm_cert_arn,
        customer_domain=customer_domain,
        env=aws_cdk.Environment(
            account=account,
            region=region,
        ),
    )
else:
    print("Required context not found: creating a default app').")
    CdkStack(
        app,
        f"SpeakCareCustomer-{customer_name}-{environment}",
    )

app.synth()

# use this command to deploy the stack

# before running cdk from local station you need to have credentianls set in your enviroment variables
# export AWS_ACCESS_KEY_ID="<access-key-id>"
# export AWS_SECRET_ACCESS_KEY="<secret-access-key>"
# export AWS_SESSION_TOKEN="<session-token>"
# get them from the aws console - note that these are temporary and will expire after a certain time

# cdk deploy  --context customer_name=<customer_name> --context environment=[dev|stage|prod] --context acm_cert_arn=<cert_arn> --context account=<account_id> --context "@aws-cdk/core:bootstrapQualifier=speakcare"
# you can get the cert_arn from the aws console or by running the get_cert.py script (python3 get_cert.py --profile <profile_name> --domain <wildcard_domain>)