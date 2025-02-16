import os
import json
import boto3
from dotenv import load_dotenv
from botocore.exceptions import ClientError
from speakcare_logging import SpeakcareLogger

if not load_dotenv("./.env"):
    print("No .env file found")
    exit(1)



class Boto3Session:
    def __init__(self, s3dirs: list):
        self.logger = SpeakcareLogger(__name__)
        self.init_env_variables()
        self.boto3_init_clients()
        self.s3_init_bucket(s3dirs)
        self.dynamodb_init_tables()


    

    def init_env_variables(self):
        # Configuration from environment variables
        self.__profile_name = os.getenv("AWS_PROFILE", "default")
        self.__s3_bucket_name = os.getenv("S3_BUKET_NAME", "speakcare-pilot")
        self.__nurses_table_name = os.getenv("NURSES_TABLE_NAME", "Nurses")
        self.__patients_table_name = os.getenv("PATIENTS_TABLE_NAME", "Patients")
        self.__dynamodb_table_names = [self.__nurses_table_name, self.__patients_table_name] # list to iterate over table names
        self.__running_local = os.getenv("RUNNING_LOCAL", "False").lower() == "true"
        self.__localstack_endpoint = os.getenv("LOCALSTACK_ENDPOINT", "http://localhost:4566")


    def boto3_init_clients(self):
        
        if self.__running_local:
            self.logger.info("Initializing clients for LocalStack...")
        else:
            self.logger.info("Initializing clients for AWS...") 
        
        endpoint_url = self.__localstack_endpoint if self.__running_local else None
        self.session = boto3.Session(profile_name=self.__profile_name)  # No profile needed for LocalStack
        self.logger.info(f"AWS region: {self.session.region_name}")

        # Configure clients to use LocalStack
        self.__s3_client = self.session.client('s3', endpoint_url=endpoint_url)
        self.__transcribe = self.session.client('transcribe', region_name=self.session.region_name)
        self.__dynamodb = self.session.resource('dynamodb', endpoint_url=endpoint_url)

        # Example: List buckets in LocalStack
        self.__buckets = self.__s3_client.list_buckets()
        self.logger.info(f"S3 Buckets: {[bucket['Name'] for bucket in self.__buckets.get('Buckets', [])]}")

    def s3_get_bucket_name(self):
        return self.__s3_bucket_name

    def s3_init_bucket(self, dirs: list = ["audio", "transcriptions", "diarizations", "texts", "wavs"]):
        # Create a new bucket
        # check if the bucket already exists
        bucket_exists = False
        for bucket in self.__s3_client.list_buckets()['Buckets']:
            if bucket['Name'] == self.__s3_bucket_name:
                bucket_exists = True
                break
        if not bucket_exists:
            self.__s3_client.create_bucket(Bucket=self.__s3_bucket_name)
            # creat directories
            self.logger.info(f"Created S3 bucket: {self.__s3_bucket_name}")

        for dir in dirs:
        # Check if the directory already exists
            response = self.__s3_client.list_objects_v2(Bucket=self.__s3_bucket_name, Prefix=f"{dir}/")
            if 'Contents' not in response:
                # Directory does not exist, create it
                self.__s3_client.put_object(Bucket=self.__s3_bucket_name, Key=f"{dir}/")
                self.logger.info(f"Created directory '{dir}/' in S3 bucket: {self.__s3_bucket_name}")
            else:
                self.logger.info(f"Directory '{dir}/' already exists in S3 bucket: {self.__s3_bucket_name}")

    def s3_upload_file_obj(self, file, key: str):
        self.__s3_client.upload_fileobj(file, self.__s3_bucket_name, key)
        self.logger.info(f"Uploaded file object to s3://{self.__s3_bucket_name}/{key}")

    def s3_upload_file(self, file_path: str, key: str):
        self.__s3_client.upload_file(file_path, self.__s3_bucket_name, key)
        self.logger.info(f"Uploaded file '{file_path}' to s3://{self.__s3_bucket_name}/{key}")
    
    def s3_append_from_file(self, file_path: str, key: str):
        try:
            # Get the existing file
            s3_file_exist = self.s3_check_file_exists(key)
            if s3_file_exist:
                # Download the existing file
                self.__s3_client.download_file(self.__s3_bucket_name, key, 'temp_file.txt')

                # Append new content to the downloaded file
                with open('temp_file.txt', 'a') as existing_file, open(file_path, 'r') as new_file:
                    existing_file.write('\n')
                    existing_file.write(new_file.read())
                
                self.s3_upload_file('temp_file.txt', key)
                os.remove('temp_file.txt')
            else:
                # File does not exist, create it
                self.s3_upload_file(file_path, key)
        except ClientError as e:
            self.logger.error(f"Error appending to file: {e}")
            raise
    
    def s3_copy_from_key(self, srcKey: str, destKey: str):
        self.__s3_client.copy_object(Bucket=self.__s3_bucket_name, CopySource=f"{self.__s3_bucket_name}/{srcKey}", Key=destKey)
        self.logger.info(f"Copied file s3://{self.__s3_bucket_name}/{srcKey} to s3://{self.__s3_bucket_name}/{destKey}")

    def s3_append_from_key(self, srcKey: str, destKey: str):
        try:
            # Get the existing file
            dest_file_exist = self.s3_check_file_exists(destKey)
            if dest_file_exist:
                # Download the existing file
                self.__s3_client.download_file(self.__s3_bucket_name, destKey, 'temp_dest_file.txt')
                self.__s3_client.download_file(self.__s3_bucket_name, srcKey, 'temp_source_file.txt')

                # Append new content to the downloaded file
                with open('temp_dest_file.txt', 'a') as existing_file, open('temp_source_file.txt', 'r') as new_file:
                    existing_file.write('\n')
                    existing_file.write(new_file.read())
                
                self.s3_upload_file('temp_dest_file.txt', destKey)
                os.remove('temp_dest_file.txt')
                os.remove('temp_source_file.txt')
            else:
                # File does not exist, create it
                self.s3_copy_from_key(Bucket=self.__s3_bucket_name, CopySource=f"{self.__s3_bucket_name}/{srcKey}", Key=destKey)
        except ClientError as e:
            self.logger.error(f"Error appending to file: {e}")
            raise
        
    def s3_download_file(self, key: str, file_path: str):
        self.__s3_client.download_file(self.__s3_bucket_name, key, file_path)
        self.logger.info(f"Downloaded file s3://{self.__s3_bucket_name}/{key} to '{file_path}'")

    def s3_get_object(self, key: str):
        return self.__s3_client.get_object(Bucket=self.__s3_bucket_name, Key=key)

    def s3_put_object(self, key: str, body: str):
        return self.__s3_client.put_object(Bucket=self.__s3_bucket_name, Key=key, Body=body)

    def s3_check_file_exists(self, key) -> bool:
        try:
            self.__s3_client.head_object(Bucket=self.__s3_bucket_name, Key=key)
            return True  # File exists
        except ClientError as e:
            return False  # File does not exist
    
    def s3_get_object_size(self, key: str) -> int:
        try:
            response = self.__s3_client.head_object(Bucket=self.__s3_bucket_name, Key=key)
            return response['ContentLength']
        except ClientError as e:
            self.logger.error(f"Error getting object size: {e}")
            raise

    def s3_get_object_content(self, key: str) -> str:
        try:
            response = self.s3_get_object(key)
            content = response['Body'].read().decode('utf-8')
            self.logger.info(f"Read content from object s3://{self.__s3_bucket_name}/{key}")
            return content
        except ClientError as e:
            self.logger.error(f"Error reading content from object s3://{self.__s3_bucket_name}/{key}: {e}")
            raise

    def dynamodb_init_tables(self):
        # Create a new table
        table_exists = False
        allTables = self.__dynamodb.tables.all()
        existing_table_names = [table.name for table in allTables]
        self.logger.info(f"init_dynamodb_tables {self.__dynamodb_table_names}: Found existing tables: {[table.name for table in allTables]}")
        for tableName in self.__dynamodb_table_names:
            self.logger.info(f"Checking if table '{tableName}' exists")
            if tableName in existing_table_names:
                self.logger.info(f"DynamoDB table '{tableName}' already exists")
                continue
            else:
                table = self.__dynamodb.create_table(
                    TableName=tableName,
                    KeySchema=[
                        {
                            'AttributeName': 'Name',
                            'KeyType': 'HASH'
                        }
                    ],
                    AttributeDefinitions=[
                        {
                            'AttributeName': 'Name',
                            'AttributeType': 'S'
                        }
                    ],
                    ProvisionedThroughput={
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                )
                table.wait_until_exists()
                self.logger.info(f"Created DynamoDB table: '{tableName}'")
        self.logger.info(f"DynamoDB done creating tables")

    def dynamo_get_table(self, table_name):
        return self.__dynamodb.Table(table_name)

    
    def get_transcribe_client(self):
        return self.__transcribe   
    
    