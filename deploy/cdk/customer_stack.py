import json
import os
from pathlib import Path
from dotenv import load_dotenv
from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
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
    RemovalPolicy,
    CfnOutput
)
from constructs import Construct
import secrets
from botocore.exceptions import ClientError
import boto3
from .swagger_html_generator import SwaggerHtmlGenerator


class SpeakCareCustomerStack(Stack):
    def __init__(self, scope: Construct, id: str, *,
                 customer_name: str,
                 environment: str,
                 acm_cert_arn: str,
                #  hosted_zone_id: str,
                 customer_domain: str,
                 aws_profile: str = None,
                 version: str = "v1",
                 space: str = "tenants",
                 **kwargs):
        super().__init__(scope, id, **kwargs)

        # Load environment variables from .env file
        env_file_path = Path(__file__).parent.parent / '.env'
        if env_file_path.exists():
            load_dotenv(env_file_path)
            print(f"Loaded environment variables from {env_file_path}")
        else:
            print(f"No .env file found at {env_file_path}")

        # Store parameters
        self.customer_name = customer_name
        self.env_ = environment
        self.version = version
        self.space = space

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
            removal_policy=RemovalPolicy.DESTROY,
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

        # --- Grant permissions to the lambda role ---
        s3_bucket.grant_put(lambda_role, "recording/*")
        s3_bucket.grant_put(lambda_role, "telemetry/*")
        enrollments_table.grant_write_data(lambda_role)
        sessions_table.grant_write_data(lambda_role)
        
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
            code=lambda_.Code.from_asset("lambda/recording_handler"),
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
            code=lambda_.Code.from_asset("lambda/recording_update_handler"),
            environment={
                "CUSTOMER_NAME": customer_name,
                "S3_RECORDING_DIR": "recording",
            },
            role=lambda_role,
            timeout=Duration.seconds(30),
            memory_size=128,
        )
        
        # Telemetry handler lambda
        telemetry_handler = lambda_.Function(
            self, f"{customer_name}-telemetry-handler",
            function_name=f"speakcare-{customer_name}-telemetry-handler",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="telemetry_handler.lambda_handler",
            code=lambda_.Code.from_asset("lambda/telemetry_handler"),
            environment={
                "CUSTOMER_NAME": customer_name,
                "S3_BUCKET": s3_bucket.bucket_name,
                "S3_TELEMETRY_DIR": "telemetry",
            },
            role=lambda_role,
            timeout=Duration.seconds(30),
            memory_size=128,
        )
        
        # New lambda handlers for watch endpoints
        nurse_handler = lambda_.Function(
            self, f"{customer_name}-nurse-handler",
            function_name=f"speakcare-{customer_name}-nurse-handler",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="nurse_handler.lambda_handler",
            code=lambda_.Code.from_asset("lambda/nurse_handler"),
            environment={
                "CUSTOMER_NAME": customer_name,
            },
            role=lambda_role,
            timeout=Duration.seconds(30),
            memory_size=128,
        )
        
        user_handler = lambda_.Function(
            self, f"{customer_name}-user-handler",
            function_name=f"speakcare-{customer_name}-user-handler",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="user_handler.lambda_handler",
            code=lambda_.Code.from_asset("lambda/user_handler"),
            environment={
                "CUSTOMER_NAME": customer_name,
            },
            role=lambda_role,
            timeout=Duration.seconds(30),
            memory_size=128,
        )
        
        shift_handler = lambda_.Function(
            self, f"{customer_name}-shift-handler",
            function_name=f"speakcare-{customer_name}-shift-handler",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="shift_handler.lambda_handler",
            code=lambda_.Code.from_asset("lambda/shift_handler"),
            environment={
                "CUSTOMER_NAME": customer_name,
                "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
                "OPENAI_STT_MODEL": os.getenv("OPENAI_STT_MODEL", "whisper-1"),
                "OPENAI_MODEL": os.getenv("OPENAI_MODEL", "gpt-4.1-nano-2025-04-14"),
                "OPENAI_TEMPERATURE": os.getenv("OPENAI_TEMPERATURE", "0.2"),
                "OPENAI_MAX_COMPLETION_TOKENS": os.getenv("OPENAI_MAX_COMPLETION_TOKENS", "4096"),
                "MAX_AUDIO_SIZE_BYTES": os.getenv("MAX_AUDIO_SIZE_BYTES", "102400"),
            },
            role=lambda_role,
            timeout=Duration.seconds(30),
            memory_size=128,
        )
        
        # Generate Swagger UI HTML and upload to S3
        swagger_html_key = "docs/swagger-ui.html"
        
        # Create a custom construct to generate Swagger HTML
        swagger_generator = SwaggerHtmlGenerator(
            self, f"{customer_name}-swagger-generator",
            s3_bucket=s3_bucket,
            html_key=swagger_html_key,
            version=version,
            space=space,
            tenant=customer_name
        )
        
        # Docs handler for Swagger UI
        docs_handler = lambda_.Function(
            self, f"{customer_name}-docs-handler",
            function_name=f"speakcare-{customer_name}-docs-handler",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="docs_handler.lambda_handler",
            code=lambda_.Code.from_asset("lambda/docs_handler"),
            environment={
                "CUSTOMER_NAME": customer_name,
                "S3_BUCKET": s3_bucket.bucket_name,
                "SWAGGER_HTML_S3_KEY": swagger_html_key,
            },
            role=lambda_role,
            timeout=Duration.seconds(30),
            memory_size=128,
        )
        
        # Grant docs handler read access to the S3 bucket
        s3_bucket.grant_read(docs_handler)
        
        # Ensure the Swagger HTML is generated before the Lambda is created
        docs_handler.node.add_dependency(swagger_generator)

        # --- API Gateway ---
        rest_api = apigw.RestApi(
            self, f"{customer_name}-api",
            rest_api_name=f"speakcare-{customer_name}-api",
            endpoint_types=[apigw.EndpointType.REGIONAL],
            deploy_options=apigw.StageOptions(stage_name=self.env_),
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
        
        # Telemetry resource
        telemetry = rest_api.root.add_resource("telemetry")

        # Methods + Proxy Integration
        enrollment.add_method("POST", apigw.LambdaIntegration(recording_handler), api_key_required=True)
        enrollment_id.add_method("PATCH", apigw.LambdaIntegration(recording_update_handler), 
                                 request_parameters={"method.request.path.recordingId": True}, api_key_required=True)
        session.add_method("POST", apigw.LambdaIntegration(recording_handler), api_key_required=True)
        session_id.add_method("PATCH", apigw.LambdaIntegration(recording_update_handler), 
                              request_parameters={"method.request.path.recordingId": True}, api_key_required=True)
        
        # Telemetry endpoint
        telemetry.add_method("POST", apigw.LambdaIntegration(telemetry_handler), api_key_required=True)

        # --- New Structured API Gateway Paths ---
        # /api/{version}/{space}/{tenant}/...
        
        # Create the structured API resources
        api = rest_api.root.add_resource("api")
        version = api.add_resource("{version}")
        space = version.add_resource("{space}")
        tenant = space.add_resource("{tenant}")
        
        # Nurses endpoint
        nurses = tenant.add_resource("nurses")
        nurses.add_method("GET", apigw.LambdaIntegration(nurse_handler), api_key_required=True)
        
        # Users endpoints
        users = tenant.add_resource("users")
        users_actions = users.add_resource("actions")
        users_enroll = users_actions.add_resource("enroll")
        users_enroll_user = users_enroll.add_resource("{userId}")
        users_enroll_user.add_method("POST", apigw.LambdaIntegration(user_handler), api_key_required=True)
        
        # Shifts endpoints
        shifts = tenant.add_resource("shifts")
        shifts_actions = shifts.add_resource("actions")
        shifts_start = shifts_actions.add_resource("start")
        shifts_start.add_method("POST", apigw.LambdaIntegration(shift_handler), api_key_required=True)
        shifts_end = shifts_actions.add_resource("end")
        shifts_end_user = shifts_end.add_resource("{userId}")
        shifts_end_user.add_method("POST", apigw.LambdaIntegration(shift_handler), api_key_required=True)
        
        # Recording endpoints (new structured versions)
        recording_structured = tenant.add_resource("recording")
        recording_structured.add_method("POST", apigw.LambdaIntegration(recording_handler), api_key_required=True)
        recording_structured_id = recording_structured.add_resource("{recordingId}")
        recording_structured_id.add_method("PATCH", apigw.LambdaIntegration(recording_update_handler), api_key_required=True)
        
        # Telemetry endpoint (new structured version)
        telemetry_structured = tenant.add_resource("telemetry")
        telemetry_structured.add_method("POST", apigw.LambdaIntegration(telemetry_handler), api_key_required=True)
        
        # Documentation endpoint (Swagger UI) - no API key required for docs
        docs = tenant.add_resource("docs")
        docs.add_method("GET", apigw.LambdaIntegration(docs_handler), api_key_required=False)


        # ------------------------------------------------------------
        # Create-or-reuse a Secrets Manager entry for the *value*
        # ------------------------------------------------------------
        secret_name = f"speakcare/{customer_name}/api-key"
        # Use the same AWS profile that was validated in app.py
        if aws_profile:
            session = boto3.Session(profile_name=aws_profile, region_name=self.region)
        else:
            session = boto3.Session(region_name=self.region)
        sm = session.client("secretsmanager")
        api_key_secret = None
        secret_id = f"{customer_name}-api-key-secret"
        try:
            sm.describe_secret(SecretId=secret_name)                 # ← fast existence test
            api_key_secret = secretsmanager.Secret.from_secret_name_v2(  # already there ➜ import
                self, secret_id, secret_name
            )      
        except ClientError as e:
            if e.response['Error']['Code'] != 'ResourceNotFoundException':
                raise e
            else:
                api_key_secret = secretsmanager.Secret(
                    self, secret_id,
                    secret_name = secret_name,
                    description = f"API key for customer {customer_name}",
                    generate_secret_string = secretsmanager.SecretStringGenerator(
                        secret_string_template = json.dumps({}),         # create empty JSON
                        generate_string_key   = "apiKeyValue",           # fill this key
                        password_length       = 43,
                        exclude_punctuation   = True,
                    ),
                    removal_policy = RemovalPolicy.RETAIN,  
                )

        api_key_value = (
            api_key_secret                       # the imported/created secret
                .secret_value_from_json("apiKeyValue")   # → SecretValue
                .unsafe_unwrap()                         # → plain string (a CFN-dynamic ref)
        )

        # ------------------------------------------------------------
        # Usage plan & ApiKey that pulls its value from the secret
        # ------------------------------------------------------------
        usage_plan = rest_api.add_usage_plan(
            f"{customer_name}-usage-plan",
            name       = f"{customer_name}-usage-plan",
            api_stages = [
                apigw.UsagePlanPerApiStage(api  = rest_api,
                                           stage = rest_api.deployment_stage)
            ],
        )

        api_key = rest_api.add_api_key(
            f"{customer_name}-api-key",
            api_key_name = f"{customer_name}-api-key",           # stable logical ID & name
            value        = api_key_value,
        )
        usage_plan.add_api_key(api_key)

        # ------------------------------------------------------------
        # Publish the ApiKey *ID* as a CloudFormation output
        #     (easy to query; value stays in the secret)
        # ------------------------------------------------------------
        CfnOutput(
            self, f"{customer_name}-api-key-id",
            value       = api_key.key_id,                        # physical ID
            export_name = f"{customer_name}-ApiKeyId"            # optional cross-stack use
        )

        # --- Custom Domain ---
        cert = acm.Certificate.from_certificate_arn(self, "acm-cert", acm_cert_arn)
        # zone = route53.HostedZone.from_hosted_zone_id(self, "hosted-zone", hosted_zone_id)
        zone = route53.HostedZone.from_lookup(
            self, "hosted-zone",
            domain_name=f"{self.env_}.speakcare.ai"
        )
        domain_name = apigw.DomainName(
            self, f"{customer_name}-domain",
            domain_name=customer_domain,
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
            record_name=customer_domain,
            target=route53.RecordTarget.from_alias(targets.ApiGatewayDomain(domain_name)),
            zone=zone,
        )

        # TODO: Add backup/retention monitoring, alarms, etc. as needed

