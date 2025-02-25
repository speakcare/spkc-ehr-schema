import os
import json
import boto3
from dotenv import load_dotenv
from botocore.exceptions import ClientError
from speakcare_logging import SpeakcareLogger
from speakcare_env import SpeakcareEnv

if not load_dotenv("./.env"):
    print("No .env file found")
    exit(1)



class Boto3Session:

    __profile_name = ""
    __s3_client = None
    __s3_bucket_name = ""
    __buckets = []
    __speakers_table_name = "" 
    __dynamodb_table_names = []
    __use_localstack = False 
    __localstack_endpoint = ""
    __is_initialized = False
    __session = None
    __dynamodb = None
    __transcribe = None
    __logger = SpeakcareLogger(__name__)

    def __init__(self, s3dirs: list):
        if not Boto3Session.__is_initialized:
            self.__logger.debug("Initializing Boto3 session...")
            self.__init_env_variables()
            self.__boto3_init_clients()
            self.__s3_init_bucket(s3dirs)
            self.__dynamodb_init_tables()
            Boto3Session.__is_initialized = True


    
    @staticmethod
    def __init_env_variables():
        # Configuration from environment variables
        Boto3Session.__profile_name = os.getenv("AWS_PROFILE", "default")
        Boto3Session.__s3_bucket_name = os.getenv("S3_BUKET_NAME", "speakcare-pilot")
        Boto3Session.__speakers_table_name = os.getenv("DYNAMODB_SPEAKERS_TABLE_NAME", "Speakers")
        Boto3Session.__dynamodb_table_names = [Boto3Session.__speakers_table_name]
        Boto3Session.__use_localstack = os.getenv("USE_LOCALSTACK", "False").lower() == "true"
        Boto3Session.__localstack_endpoint = os.getenv("LOCALSTACK_ENDPOINT", "http://localhost:4566")


    @staticmethod
    def __boto3_init_clients(): 
        if Boto3Session.__use_localstack:
            Boto3Session.__logger.debug("Initializing clients for LocalStack...")
        else:
            Boto3Session.__logger.debug("Initializing clients for AWS...") 
        
        endpoint_url = Boto3Session.__localstack_endpoint if Boto3Session.__use_localstack else None
        Boto3Session.__session = boto3.Session(profile_name=Boto3Session.__profile_name)  # No profile needed for LocalStack
        Boto3Session.__logger.debug(f"AWS region: {Boto3Session.__session.region_name}")

        # Configure clients to use LocalStack
        Boto3Session.__s3_client = Boto3Session.__session.client('s3', endpoint_url=endpoint_url)
        Boto3Session.__transcribe = Boto3Session.__session.client('transcribe', region_name=Boto3Session.__session.region_name)
        Boto3Session.__dynamodb = Boto3Session.__session.resource('dynamodb', endpoint_url=endpoint_url)

        # Example: List buckets in LocalStack
        Boto3Session.__buckets = Boto3Session.__s3_client.list_buckets()
        Boto3Session.__logger.debug(f"S3 Buckets: {[bucket['Name'] for bucket in Boto3Session.__buckets.get('Buckets', [])]}")

    @staticmethod
    def __s3_init_bucket(dirs: list = []):
        # Create a new bucket
        # check if the bucket already exists
        bucket_exists = False
        for bucket in Boto3Session.__s3_client.list_buckets()['Buckets']:
            if bucket['Name'] == Boto3Session.__s3_bucket_name:
                bucket_exists = True
                break
        if not bucket_exists:
            Boto3Session.__logger.info(f"Creating S3 bucket: {Boto3Session.__s3_bucket_name}")
            Boto3Session.__s3_client.create_bucket(Bucket=Boto3Session.__s3_bucket_name)
            # creat directories
            Boto3Session.__logger.info(f"Created S3 bucket: {Boto3Session.__s3_bucket_name}")

        for dir in dirs:
        # Check if the directory already exists
            response = Boto3Session.__s3_client.list_objects_v2(Bucket=Boto3Session.__s3_bucket_name, Prefix=f"{dir}/")
            if 'Contents' not in response:
                # Directory does not exist, create it
                Boto3Session.__s3_client.put_object(Bucket=Boto3Session.__s3_bucket_name, Key=f"{dir}/")
                Boto3Session.__logger.debug(f"Created directory '{dir}/' in S3 bucket: {Boto3Session.__s3_bucket_name}")
            else:
                Boto3Session.__logger.debug(f"Directory '{dir}/' already exists in S3 bucket: {Boto3Session.__s3_bucket_name}")

    def s3_get_bucket_name(self):
        return self.__s3_bucket_name


    def s3_upload_file_obj(self, file, key: str):
        self.__s3_client.upload_fileobj(file, self.__s3_bucket_name, key)
        self.__logger.debug(f"Uploaded file object to s3://{self.__s3_bucket_name}/{key}")

    def s3_upload_file(self, file_path: str, key: str):
        self.__s3_client.upload_file(file_path, self.__s3_bucket_name, key)
        self.__logger.debug(f"Uploaded file '{file_path}' to s3://{self.__s3_bucket_name}/{key}")
    
    def s3_append_from_file(self, file_path: str, key: str):
        try:
            # Get the existing file
            s3_file_exist = self.s3_check_object_exists(key)
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
            self.__logger.error(f"Error appending to file: {e}")
            raise
    
    def s3_copy_object(self, srcKey: str, destKey: str):
        self.__s3_client.copy_object(Bucket=self.__s3_bucket_name, CopySource=f"{self.__s3_bucket_name}/{srcKey}", Key=destKey)
        self.__logger.debug(f"Copied file s3://{self.__s3_bucket_name}/{srcKey} to s3://{self.__s3_bucket_name}/{destKey}")

    def s3_append_from_key(self, srcKey: str, destKey: str):
        try:
            # Get the existing file
            dest_file_exist = self.s3_check_object_exists(destKey)
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
                self.s3_copy_object(Bucket=self.__s3_bucket_name, CopySource=f"{self.__s3_bucket_name}/{srcKey}", Key=destKey)
        except ClientError as e:
            self.__logger.error(f"Error appending to file: {e}")
            raise
        
    def s3_download_file(self, key: str, file_path: str):
        self.__s3_client.download_file(self.__s3_bucket_name, key, file_path)
        self.__logger.info(f"Downloaded file s3://{self.__s3_bucket_name}/{key} to '{file_path}'")

    def s3_get_object(self, key: str):
        return self.__s3_client.get_object(Bucket=self.__s3_bucket_name, Key=key)

    def s3_put_object(self, key: str, body: str):
        return self.__s3_client.put_object(Bucket=self.__s3_bucket_name, Key=key, Body=body)

    def s3_check_object_exists(self, key) -> bool:
        try:
            self.__logger.debug(f"Checking if file exists: s3://{self.__s3_bucket_name}/{key}")
            self.__s3_client.head_object(Bucket=self.__s3_bucket_name, Key=key)
            return True  # File exists
        except ClientError as e:
            return False  # File does not exist
    
    def s3_get_object_size(self, key: str) -> int:
        try:
            response = self.__s3_client.head_object(Bucket=self.__s3_bucket_name, Key=key)
            return response['ContentLength']
        except ClientError as e:
            self.__logger.error(f"Error getting object size: {e}")
            raise

    def s3_get_object_content(self, key: str) -> str:
        try:
            response = self.s3_get_object(key)
            content = response['Body'].read().decode('utf-8')
            self.__logger.info(f"Read content from object s3://{self.__s3_bucket_name}/{key}")
            return content
        except ClientError as e:
            self.__logger.error(f"Error reading content from object s3://{self.__s3_bucket_name}/{key}: {e}")
            raise

    def s3_get_object_last_modified(self, key: str):
        try:
            response = self.__s3_client.head_object(Bucket=self.__s3_bucket_name, Key=key)
            return response['LastModified']
        except ClientError as e:
            self.__logger.error(f"Error getting object last modified time: {e}")
            raise

    def s3_list_folder(self, folder_prefix: str):
        """List all objects in a specific folder in the S3 bucket."""
        try:
            response = self.__s3_client.list_objects_v2(Bucket=self.__s3_bucket_name, Prefix=folder_prefix)
            if 'Contents' in response:
                objects = [obj['Key'] for obj in response['Contents']]
                self.__logger.info(f"Listed {len(objects)} objects in folder s3://{self.__s3_bucket_name}/{folder_prefix}")
                return objects
            else:
                self.__logger.info(f"No objects found in folder s3://{self.__s3_bucket_name}/{folder_prefix}")
                return []
        except ClientError as e:
            self.__logger.error(f"Error listing objects in folder s3://{self.__s3_bucket_name}/{folder_prefix}: {e}")
            raise

    def s3_get_file_path(self, key: str):
        return f"s3://{self.__s3_bucket_name}/{key}"

    @staticmethod
    def s3_extract_key(s3_url):
        """Extract the path from an S3 URL."""
        if s3_url.startswith("s3://"):
            # Remove the 's3://' prefix
            s3_url = s3_url[5:]
            # Find the first '/' after the bucket name
            key_start = s3_url.find('/')
            if key_start != -1:
                # Extract the path
                return s3_url[key_start + 1:]
        return None


    @staticmethod
    def __dynamodb_init_tables():
        # Create a new table
        table_exists = False
        allTables = Boto3Session.__dynamodb.tables.all()
        existing_table_names = [table.name for table in allTables]
        Boto3Session.__logger.debug(f"init_dynamodb_tables {Boto3Session.__dynamodb_table_names}: Found existing tables: {[table.name for table in allTables]}")
        for tableName in Boto3Session.__dynamodb_table_names:
            Boto3Session.__logger.debug(f"Checking if table '{tableName}' exists")
            if tableName in existing_table_names:
                Boto3Session.__logger.debug(f"DynamoDB table '{tableName}' already exists")
                continue
            else:
                table = Boto3Session.__dynamodb.create_table(
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
                Boto3Session.__logger.debug(f"Created DynamoDB table: '{tableName}'")
        Boto3Session.__logger.debug(f"DynamoDB done creating tables")

    def dynamo_get_table(self, table_name):
        return self.__dynamodb.Table(table_name)
    
    def dynamo_get_table_name(self, table_name: str = '') -> str:
        table_name = table_name.lower()
        if table_name == 'speakers':
            return self.__speakers_table_name
        else:
            return None

    
    def get_transcribe_client(self):
        return self.__transcribe  
    
    