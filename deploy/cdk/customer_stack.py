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
    RemovalPolicy,
    CfnOutput
)
from constructs import Construct
import secrets
from botocore.exceptions import ClientError
import boto3




class SpeakCareCustomerStack(Stack):
    def __init__(self, scope: Construct, id: str, *,
                 customer_name: str,
                 environment: str,
                 acm_cert_arn: str,
                #  hosted_zone_id: str,
                 customer_domain: str,
                 aws_profile: str = None,
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
            domain_name=f"{environment}.speakcare.ai"
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

