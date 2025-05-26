import os
import boto3
import argparse

def get_acm_cert_arn_by_wildcard(domain_wildcard, profile=None):
    """Look up ACM cert ARN matching a wildcard domain (e.g., '*.api.dev.speakcare.ai')."""
    session = boto3.Session(profile_name=profile)
    acm = session.client('acm')
    paginator = acm.get_paginator('list_certificates')
    for page in paginator.paginate(CertificateStatuses=['ISSUED']):
        for cert in page['CertificateSummaryList']:
            if cert.get('DomainName') == domain_wildcard:
                return cert['CertificateArn']
    return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Get ACM cert ARN by wildcard domain')
    parser.add_argument('--profile', type=str, default=os.environ.get("AWS_PROFILE", "default"), help='AWS profile name')
    parser.add_argument('--domain', type=str, default="*.api.dev.speakcare.ai", help='Wildcard domain')
    args = parser.parse_args()
    
    profile = args.profile
    domain_wildcard = args.domain

    print(f"Profile: {profile}")
    print(f"Domain: {domain_wildcard}")
    cert_arn = get_acm_cert_arn_by_wildcard(domain_wildcard, profile)
    print(f"Found ACM cert ARN: {cert_arn}")