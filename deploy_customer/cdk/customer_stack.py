import json
from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_apigateway as apigw,
    aws_secretsmanager as secretsmanager,
    aws_certificatemanager as acm,
    aws_route53 as route53,
    aws_route53_targets as targets,
    Duration,
    SecretValue,
    RemovalPolicy
)
from constructs import Construct

class SpeakCareCustomerStack(Stack):
    def __init__(self, scope: Construct, id: str, *,
                 customer_name: str,
                 environment: str,
                 acm_cert_arn: str,
                #  hosted_zone_id: str,
                 domain: str,
                 **kwargs):
        super().__init__(scope, id, **kwargs)

        # --- S3 Bucket ---
        s3_bucket = s3.Bucket(
            self, f"{customer_name}-bucket",
            bucket_name=f"speakcare-cust-{customer_name}",
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY, # TODO: Understand this !!! Change to RETAIN for prod!
            auto_delete_objects=True,                # Only for dev/demo!
        )

        # --- DynamoDB Tables ---
        enrollments_table = dynamodb.Table(
            self, f"{customer_name}-enrollments-table",
            table_name=f"{customer_name}-recordings-enrollments",
            partition_key=dynamodb.Attribute(name="recordingId", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="expiresAt",
            removal_policy=RemovalPolicy.DESTROY, # TODO: Change to RETAIN for prod!
        )
        sessions_table = dynamodb.Table(
            self, f"{customer_name}-sessions-table",
            table_name=f"{customer_name}-recordings-sessions",
            partition_key=dynamodb.Attribute(name="recordingId", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="expiresAt",
            removal_policy=dynamodb.RemovalPolicy.DESTROY,
        )

        # --- IAM Role for Lambda ---
        lambda_role = iam.Role(
            self, f"{customer_name}-lambda-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            role_name=f"speakcare-{customer_name}-recording-lambda-role",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
            ]
        )
        # Custom policy: Allow s3:PutObject and dynamodb:PutItem,UpdateItem
        lambda_role.add_to_policy(iam.PolicyStatement(
            actions=["s3:PutObject"],
            resources=[f"{s3_bucket.bucket_arn}/recording/*"],
        ))
        lambda_role.add_to_policy(iam.PolicyStatement(
            actions=["dynamodb:PutItem", "dynamodb:UpdateItem"],
            resources=[enrollments_table.table_arn, sessions_table.table_arn],
        ))

        # --- Lambda Functions ---
        lambda_env = {
            "CUSTOMER_NAME": customer_name,
            "S3_BUCKET": s3_bucket.bucket_name,
            "S3_RECORDING_DIR": "recording",
            "UPLOAD_EXPIRES": str(1*3600),
            "PRESIGN_URL_EXPIRES": str(5*60),
        }
        recording_handler = lambda_.Function(
            self, f"{customer_name}-recording-handler",
            function_name=f"speakcare-{customer_name}-recording-handler",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="recording_handler.lambda_handler",
            code=lambda_.Code.from_asset("../lambda", include=["recording_handler.py"]),
            environment=lambda_env,
            role=lambda_role,
            timeout=Duration.seconds(30),
            memory_size=128,
        )
        recording_update_handler = lambda_.Function(
            self, f"{customer_name}-recording-update-handler",
            function_name=f"speakcare-{customer_name}-recording-update-handler",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="recording_update_handler.lambda_handler",
            code=lambda_.Code.from_asset("../lambda", include=["recording_update_handler.py"]),
            environment={
                "CUSTOMER_NAME": customer_name,
                "S3_RECORDING_DIR": "recording",
            },
            role=lambda_role,
            timeout=Duration.seconds(30),
            memory_size=128,
        )
        # TODO: need code update and config update

        # --- API Gateway ---
        rest_api = apigw.RestApi(
            self, f"{customer_name}-api",
            rest_api_name=f"speakcare-{customer_name}-api",
            endpoint_types=[apigw.EndpointType.REGIONAL],
            deploy_options=apigw.StageOptions(stage_name=environment),
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
            ),
        )
        # Resources
        recording = rest_api.root.add_resource("recording")
        enrollment = recording.add_resource("enrollment")
        enrollment_id = enrollment.add_resource("{recordingId}")
        session = recording.add_resource("session")
        session_id = session.add_resource("{recordingId}")

        # Methods + Proxy Integration
        enrollment.add_method("POST", apigw.LambdaIntegration(recording_handler), api_key_required=True)
        enrollment_id.add_method("PATCH", apigw.LambdaIntegration(recording_update_handler), 
                                 request_parameters={"method.request.path.recordingId": True}, api_key_required=True)
        session.add_method("POST", apigw.LambdaIntegration(recording_handler), api_key_required=True)
        session_id.add_method("PATCH", apigw.LambdaIntegration(recording_update_handler), 
                              request_parameters={"method.request.path.recordingId": True}, api_key_required=True)

        # --- Usage Plan & API Key ---
        usage_plan = rest_api.add_usage_plan(
            f"{customer_name}-usage-plan",
            name=f"{customer_name}-usage-plan",
            api_stages=[apigw.UsagePlanPerApiStage(api=rest_api, stage=rest_api.deployment_stage)],
        )
        api_key = rest_api.add_api_key(f"{customer_name}-api-key")
        usage_plan.add_api_key(api_key)

        # Store API key in Secrets Manager
        secretsmanager.Secret(
            self, f"{customer_name}-api-key-secret",
            secret_name=f"speakcare/{customer_name}/api-key",
            description=f"API key for customer {customer_name} audio ingestion",
            secret_string_value=SecretValue.unsafe_plain_text(
                json.dumps({
                    "apiKeyId": api_key.key_id,
                    "apiKeyValue": api_key.key_value
        })
    ),
)
        # TODO: where is the key id?

        # --- Custom Domain ---
        cert = acm.Certificate.from_certificate_arn(self, "acm-cert", acm_cert_arn)
        # zone = route53.HostedZone.from_hosted_zone_id(self, "hosted-zone", hosted_zone_id)
        zone = route53.HostedZone.from_lookup(
            self, "hosted-zone",
            domain_name=f"{environment}.speakcare.ai"
        )
        domain_name = apigw.DomainName(
            self, f"{customer_name}-domain",
            domain_name=domain,
            certificate=cert,
            endpoint_type=apigw.EndpointType.REGIONAL,
            security_policy=apigw.SecurityPolicy.TLS_1_2,
        )
        # Base path mapping
        apigw.BasePathMapping(
            self, f"{customer_name}-base-path-mapping",
            domain_name=domain_name,
            rest_api=rest_api,
            stage=rest_api.deployment_stage,
        )
        # Route53 Alias
        route53.ARecord(
            self, f"{customer_name}-api-alias",
            record_name=domain,
            target=route53.RecordTarget.from_alias(targets.ApiGatewayDomain(domain_name)),
            zone=zone,
        )

        # TODO: Add backup/retention monitoring, alarms, etc. as needed

