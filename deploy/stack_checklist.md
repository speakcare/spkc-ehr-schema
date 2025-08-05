# SpeakCare Customer CDK Stack Checklist

| #  | Resource/Step                       | Included in CDK? | Notes/Details                                                     |
|----|-------------------------------------|:----------------:|-------------------------------------------------------------------|
| 1  | S3 Bucket (per customer)            |       ✅         | Versioned, named `speakcare-{customer_name}`                      |
| 2  | DynamoDB Table: Enrollments         |       ✅         | TTL on `expiresAt`, named `{customer_name}-recordings-enrollments`|
| 3  | DynamoDB Table: Sessions            |       ✅         | TTL on `expiresAt`, named `{customer_name}-recordings-sessions`   |
| 4  | IAM Role for Lambda                 |       ✅         | Trusts Lambda, includes S3 & DynamoDB inline policy               |
| 5  | Lambda Function: recording_handler  |       ✅         | Bundled from `lambda/`, env vars per customer                     |
| 6  | Lambda Function: recording_update_handler |   ✅         | Bundled from `lambda/`, env vars per customer                     |
| 7  | API Gateway REST API                |       ✅         | Includes resource paths, methods, proxy integration               |
| 8  | API Gateway Resources & Methods     |       ✅         | `/recording/enrollment`, `/session`, POST/PATCH, API key required |
| 9  | Usage Plan & API Key                |       ✅         | API key created, attached to usage plan                           |
| 10 | API Key stored in Secrets Manager   |       ✅         | Secret is JSON: `{apiKeyId, apiKeyValue}`                         |
| 11 | Custom Domain for API Gateway       |       ✅         | Uses shared ACM cert ARN, one per customer                        |
| 12 | Base Path Mapping                   |       ✅         | Maps custom domain to API/stage                                   |
| 13 | Route53 A Record for Domain         |       ✅         | Alias points to API Gateway custom domain                         |
| 14 | Lambda Permissions for API Gateway  |       ✅         | CDK auto-adds invoke permissions                                  |
| 15 | Lambda Code Packaging/Deploy        |       ✅         | CDK auto-bundles from local source                                |
| 16 | Removal Policy on Data Resources    |   ⚠️ (DESTROY)   | Set to `DESTROY` for dev/testing; set `RETAIN` for production     |
| 17 | ACM Certificate (shared)            |       ❌         | Not in stack; referenced via ARN; managed out-of-band             |
| 18 | Route53 Hosted Zone (shared)        |       ❌         | Not in stack; referenced via ID; managed out-of-band              |
| 19 | ACM DNS Validation Records          |       ❌         | Managed once per environment, not per customer                    |
| 20 | Backup/Retention Policies           |       ❌         | To be added in future (not in CDK stack yet)                      |

