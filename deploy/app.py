#!/usr/bin/env python3
import os
import sys
import boto3
import argparse

import aws_cdk

from cdk.customer_stack import SpeakCareCustomerStack
from cdk.cdk_stack import CdkStack
from get_cert import get_acm_cert_arn_by_wildcard


def get_aws_session_info(profile_name=None):
    """Get AWS account and region from the current AWS session/profile"""
    try:
        session = boto3.Session(profile_name=profile_name)
        sts = session.client('sts')
        identity = sts.get_caller_identity()
        
        # Get region from session
        region = session.region_name
        if not region:
            # Fallback to default region
            region = 'us-east-1'
            
        return {
            'account': identity['Account'],
            'region': region,
            'profile': profile_name or 'default'
        }
    except Exception as e:
        print(f"Error getting AWS session info: {e}")
        print("Make sure you're logged in with AWS SSO or have valid credentials configured")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='Deploy SpeakCare CDK Stack')
    parser.add_argument('--customer-name', required=True, help='Customer name (e.g., holyname, nursing)')
    parser.add_argument('--environment', required=True, choices=['dev', 'stage', 'prod'], 
                       help='Environment (dev, stage, or prod)')
    parser.add_argument('--profile', type=str, default=os.environ.get("AWS_PROFILE", "default"), 
                       help='AWS profile name (default: from AWS_PROFILE env var or "default")')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be deployed without actually deploying')
    
    args = parser.parse_args()
    
    print(f"🚀 Deploying SpeakCare for customer: {args.customer_name}")
    print(f"📦 Environment: {args.environment}")
    print(f"🔐 AWS Profile: {args.profile}")
    
    # Get AWS session info
    aws_info = get_aws_session_info(args.profile)
    print(f"🏢 AWS Account: {aws_info['account']}")
    print(f"🌍 AWS Region: {aws_info['region']}")
    
    # Build domain names
    api_domain = f"api.{args.environment}.speakcare.ai"
    customer_domain = f"{args.customer_name}.{api_domain}"
    wildcard_domain = f"*.{api_domain}"
    
    print(f"🌐 API Domain: {api_domain}")
    print(f"🏠 Customer Domain: {customer_domain}")
    print(f"🔍 Looking for certificate: {wildcard_domain}")
    
    # Get ACM certificate ARN
    acm_cert_arn = get_acm_cert_arn_by_wildcard(wildcard_domain, args.profile)
    if not acm_cert_arn:
        print(f"❌ Error: No ACM certificate found for domain '{wildcard_domain}'")
        print("Make sure the certificate exists and is in the 'ISSUED' status")
        sys.exit(1)
    
    print(f"✅ Found ACM certificate: {acm_cert_arn}")
    
    if args.dry_run:
        print("\n🔍 DRY RUN - Would deploy:")
        print(f"   Stack: SpeakCareCustomer-{args.customer_name}-{args.environment}")
        print(f"   Customer: {args.customer_name}")
        print(f"   Environment: {args.environment}")
        print(f"   Domain: {customer_domain}")
        print(f"   Certificate: {acm_cert_arn}")
        print(f"   Account: {aws_info['account']}")
        print(f"   Region: {aws_info['region']}")
        return
    
    # Create CDK app directly
    app = aws_cdk.App()
    
    # Deploy the customer stack
    SpeakCareCustomerStack(
        app,
        f"SpeakCareCustomer-{args.customer_name}-{args.environment}",
        customer_name=args.customer_name,
        environment=args.environment,
        acm_cert_arn=acm_cert_arn,
        customer_domain=customer_domain,
        aws_profile=args.profile,
        env=aws_cdk.Environment(
            account=aws_info['account'],
            region=aws_info['region'],
        ),
    )
    
    app.synth()


if __name__ == "__main__":
    main()