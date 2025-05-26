#!/usr/bin/env python3
import os
import boto3

# import aws_cdk

# # from cdk.cdk_stack import CdkStack
# from cdk.customer_stack import SpeakCareCustomerStack
# # ...rest of your deployment logic



# app = aws_cdk.App()

# # Get params from env or context
# customer_name = app.node.try_get_context("customer_name") or os.environ.get("CUSTOMER_NAME")
# environment = app.node.try_get_context("environment") or os.environ.get("SPEAKCARE_ENV", "dev")
# acm_cert_arn = app.node.try_get_context("acm_cert_arn") or os.environ.get("ACM_CERT_ARN")
# # hosted_zone_id = app.node.try_get_context("hosted_zone_id") or os.environ.get("HOSTED_ZONE_ID")
# domain = f"{customer_name}.api.{environment}.speakcare.ai"

# SpeakCareCustomerStack(
#     app,
#     f"SpeakCareCustomer-{customer_name}-{environment}",
#     customer_name=customer_name,
#     environment=environment,
#     acm_cert_arn=acm_cert_arn,
#     # hosted_zone_id=hosted_zone_id,
#     domain=domain,
#     env=aws_cdk.Environment(
#         account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
#         region=os.environ.get("CDK_DEFAULT_REGION"),
#     ),
# )

# app.synth()

def get_aws_region_from_profile(profile_name):
    """Get AWS region from a profile (if set in ~/.aws/config) or return default region."""
    session = boto3.Session(profile_name=profile_name)
    region = session.region_name
    if not region:
        # fallback to AWS_DEFAULT_REGION env variable, or default 'us-east-1'
        region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    return region

def get_acm_cert_arn_by_wildcard(profile, domain_wildcard, region=None):
    """Look up ACM cert ARN matching a wildcard domain (e.g., '*.api.dev.speakcare.ai')."""
    session = boto3.Session(profile_name=profile, region_name=region)
    acm = session.client('acm')
    paginator = acm.get_paginator('list_certificates')
    for page in paginator.paginate(CertificateStatuses=['ISSUED']):
        for cert in page['CertificateSummaryList']:
            if cert.get('DomainName') == domain_wildcard:
                return cert['CertificateArn']
    return None

if __name__ == "__main__":
    profile = "speakcare.dev"
    domain_wildcard = "*.api.dev.speakcare.ai"
    region = get_aws_region_from_profile(profile)
    cert_arn = get_acm_cert_arn_by_wildcard(profile, domain_wildcard, region)
    print(f"Found ACM cert ARN: {cert_arn}")