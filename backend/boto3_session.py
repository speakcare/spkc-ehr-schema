import os
import json
import boto3
from botocore.exceptions import ClientError
from speakcare_logging import SpeakcareLogger
from speakcare_env import SpeakcareEnv
import urllib.parse
from os_utils import os_ensure_file_directory_exists, os_sanitize_name



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
    __single_instance = None

    def __init__(self):
        if not Boto3Session.__is_initialized:
            self.__logger.debug("Initializing Boto3 session...")
            self.__init_env_variables()
            self.__boto3_init_clients()
            self.__s3_init_bucket(SpeakcareEnv.get_working_dirs())
            self.__dynamodb_init_tables()
            Boto3Session.__is_initialized = True


    @staticmethod
    def get_single_instance():
        if Boto3Session.__single_instance is None:
            Boto3Session.__single_instance = Boto3Session()
        return Boto3Session.__single_instance
    
    @staticmethod
    def __init_env_variables():
        # Configuration from environment variables
        Boto3Session.__profile_name = os.getenv("AWS_PROFILE", "default")
        Boto3Session.__logger.info(f"AWS profile: {Boto3Session.__profile_name}")
        Boto3Session.__s3_bucket_name = os.getenv("S3_BUKET_NAME", "speakcare-pilot")
        # the speakers table name is based on the vocoder model as switching the model will require a new table
        Boto3Session.__speakers_table_name = \
            os_sanitize_name(f'{os.getenv("DYNAMODB_SPEAKERS_TABLE_NAME", "Speakers")}-{os.getenv("VOCODER_MODEL", "default")}')
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
        try:
            self.__s3_client.upload_fileobj(file, self.__s3_bucket_name, key)
        except ClientError as e:
            self.__logger.error(f"Error uploading file object to s3://{self.__s3_bucket_name}/{key}: {e}")
            raise
        self.__logger.debug(f"Uploaded file object to s3://{self.__s3_bucket_name}/{key}")


    def s3_upload_file(self, file_path: str, key: str):
        try:
            self.__s3_client.upload_file(file_path, self.__s3_bucket_name, key)
        except ClientError as e:
            self.__logger.error(f"Error uploading file '{file_path}' to 's3://{self.__s3_bucket_name}/{key}': {e}")
            raise
        self.__logger.debug(f"Uploaded file '{file_path}' to 's3://{self.__s3_bucket_name}/{key}'")
    
   
    def s3_append_from_file(self, file_path: str, key: str):
        temp_file_name = f'{SpeakcareEnv.get_local_downloads_dir()}/temp_file.txt'
        try:
            # Get the existing file
            s3_file_exist = self.s3_check_object_exists(key)
            if s3_file_exist:
                # Download the existing file
                self.__s3_client.download_file(self.__s3_bucket_name, key, temp_file_name)

                # Append new content to the downloaded file
                with open(temp_file_name, 'a') as existing_file, open(file_path, 'r') as new_file:
                    existing_file.write('\n')
                    existing_file.write(new_file.read())
                
                self.s3_upload_file(temp_file_name, key)
                os.remove(temp_file_name)
            else:
                # File does not exist, create it
                self.s3_upload_file(file_path, key)
        except ClientError as e:
            self._logger.error(f"Error appending file '{file_path}' to 's3://{self.__s3_bucket_name}/{key}': {e}")
            raise
        finally:
            if os.path.isfile(temp_file_name):
                os.remove(temp_file_name)


    def s3_copy_object(self, srcKey: str, destKey: str):
        self.__logger.debug(f"Copying file s3://{self.__s3_bucket_name}/{srcKey} to 's3://{self.__s3_bucket_name}/{destKey}'")
        try:
            self.__s3_client.copy_object(Bucket=self.__s3_bucket_name, CopySource=f"{self.__s3_bucket_name}/{srcKey}", Key=destKey)
        except ClientError as e:
            self.__logger.error(f"Error copying file 's3://{self.__s3_bucket_name}/{srcKey}' to 's3://{self.__s3_bucket_name}/{destKey}': {e}")
            raise
        self.__logger.debug(f"Copied file s3://{self.__s3_bucket_name}/{srcKey} to 's3://{self.__s3_bucket_name}/{destKey}'")

    def s3_append_from_key(self, srcKey: str, destKey: str):
        temp_dest_file = f'{SpeakcareEnv.get_local_downloads_dir()}/temp_dest_file.txt'
        temp_source_file = f'{SpeakcareEnv.get_local_downloads_dir()}/temp_source_file.txt'
        try:
            # Get the existing file
            dest_file_exist = self.s3_check_object_exists(destKey)
            if dest_file_exist:
                # Download the existing file
                self.__s3_client.download_file(self.__s3_bucket_name, destKey, temp_dest_file)
                self.__s3_client.download_file(self.__s3_bucket_name, srcKey, temp_source_file)

                # Append new content to the downloaded file
                with open(temp_dest_file, 'a') as existing_file, open(temp_source_file, 'r') as new_file:
                    existing_file.write('\n')
                    existing_file.write(new_file.read())
                
                self.s3_upload_file(temp_dest_file, destKey)
                os.remove(temp_dest_file)
                os.remove(temp_source_file)
            else:
                # File does not exist, create it
                self.s3_copy_object(srcKey, destKey)
        except ClientError as e:
            self.__logger.error(f"Error appending to file 's3://{self.__s3_bucket_name}/{srcKey}' to 's3://{self.__s3_bucket_name}/{destKey}': {e}")
            raise
        finally:
            if os.path.isfile(temp_dest_file):
                os.remove(temp_dest_file)
            if os.path.isfile(temp_source_file):
                os.remove(temp_source_file)
    

        
    def s3_download_file(self, key: str, file_path: str, bucket:str = None):
        bucket = bucket if bucket else self.__s3_bucket_name
        try:
            self.__s3_client.download_file(bucket, key, file_path)
        except ClientError as e:
            self.__logger.error(f"Error downloading file 's3://{bucket}/{key}' to '{file_path}': {e}")
            raise
        self.__logger.debug(f"Downloaded file s3://{bucket}/{key} to '{file_path}'")


    def s3_get_object_uri(self, key: str, bucket:str = None) -> str:
        bucket = bucket if bucket else self.__s3_bucket_name
        return f"s3://{bucket}/{key}"
    
    def s3_uri_download_file(self, uri: str, file_path: str):
        key = Boto3Session.s3_extract_key(uri)
        bucket = Boto3Session.s3_extract_bucket(uri)
        self.s3_download_file(key=key, file_path=file_path, bucket=bucket)

    def s3_get_object(self, key: str, bucket:str = None):
        bucket = bucket if bucket else self.__s3_bucket_name
        try:
            return self.__s3_client.get_object(Bucket=bucket, Key=key)
        except ClientError as e:
            self.__logger.error(f"Error getting object 's3://{bucket}/{key}': {e}")
            raise
    
    def s3_get_object_content(self, key: str, bucket:str = None) -> str:
        try:
            bucket = bucket if bucket else self.__s3_bucket_name
            response = self.s3_get_object(key=key, bucket=bucket)
            content = response['Body'].read().decode('utf-8')
            self.__logger.debug(f"Read content from object s3://{bucket}/{key}")
            return content
        except ClientError as e:
            self.__logger.error(f"Error reading content from object s3://{bucket}/{key}: {e}")
            raise

    def s3_uri_get_object_content(self, uri) -> str:
        key = Boto3Session.s3_extract_key(uri)
        bucket = Boto3Session.s3_extract_bucket(uri)
        return self.s3_get_object_content(key=key, bucket=bucket)


    def s3_get_object_content_json(self, key: str, bucket:str = None):
        content = self.s3_get_object_content(key=key, bucket=bucket)
        return json.loads(content)
    
    def s3_uri_get_object_content_json(self, uri) -> str:
        key = Boto3Session.s3_extract_key(uri)
        bucket = Boto3Session.s3_extract_bucket(uri)
        return self.s3_get_object_content_json(key=key, bucket=bucket)
    

    def s3_put_object(self, key: str, body: str, bucket:str = None):
        bucket = bucket if bucket else self.__s3_bucket_name
        try:
            return self.__s3_client.put_object(Bucket=bucket, Key=key, Body=body)
        except ClientError as e:
            self.__logger.error(f"Error putting object 's3://{bucket}/{key}': {e}")
            raise

    def s3_uri_put_object(self, uri: str, body: str):
        key = Boto3Session.s3_extract_key(uri)
        bucket = Boto3Session.s3_extract_bucket(uri)
        self.s3_put_object(key=key, body=body, bucket=bucket)

    def s3_check_object_exists(self, key:str, bucket:str =None) -> bool:
        try:
            bucket = bucket if bucket else self.__s3_bucket_name
            self.__logger.debug(f"Checking if file exists: s3://{bucket}/{key}")
            self.__s3_client.head_object(Bucket=bucket, Key=key)
            return True  # File exists
        except ClientError as e:
             # File does not exist
            return False 
    

    def s3_uri_check_object_exists(self, uri) -> bool:
        key = Boto3Session.s3_extract_key(uri)
        bucket = Boto3Session.s3_extract_bucket(uri)
        return self.s3_check_object_exists(key=key, bucket=bucket)

    def s3_get_object_size(self, key: str, bucket:str = None) -> int:
        try:
            bucket = bucket if bucket else self.__s3_bucket_name
            response = self.__s3_client.head_object(Bucket=bucket, Key=key)
            return response['ContentLength']
        except ClientError as e:
            self.__logger.error(f"Error getting object size 's3://{bucket}/{key}': {e}")
            raise
    
    def s3_uri_get_object_size(self, uri) -> int:
        key = Boto3Session.s3_extract_key(uri)
        bucket = Boto3Session.s3_extract_bucket(uri)
        return self.s3_get_object_size(key=key, bucket=bucket)


    def s3_get_object_last_modified(self, key: str, bucket:str = None):
        bucket = bucket if bucket else self.__s3_bucket_name
        try:
            response = self.__s3_client.head_object(Bucket=bucket, Key=key)
            return response['LastModified']
        except ClientError as e:
            self.__logger.error(f"Error getting object last modified time: {e}")
            raise

    def s3_uri_get_object_last_modified(self, uri):
        key = Boto3Session.s3_extract_key(uri)
        bucket = Boto3Session.s3_extract_bucket(uri)
        return self.s3_get_object_last_modified(key=key, bucket=bucket)

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

    def s3_get_file_uri(self, key: str):
        return f"s3://{self.__s3_bucket_name}/{key}"
    
    ''' 
        s3_localize_file_path
        Check if file is s3 path then download to local file.
        Otherwise return the local file path.
        Validated existance of file in both cases.
    '''
    
    def s3_localize_file(self, file_path: str):
        remove_local_file = False
        if file_path.startswith("s3://"):
            try:
                if self.s3_uri_check_object_exists(file_path):
                    local_file = f'{SpeakcareEnv.get_local_downloads_dir()}/{os.path.basename(file_path)}'
                    os_ensure_file_directory_exists(local_file)
                    self.s3_uri_download_file(file_path, local_file)
                    remove_local_file = True
                    self.__logger.debug(f"Downloaded audio file {file_path} to {local_file}")
                else:
                    self.__logger.error(f"s3 file {file_path} not found")
                    return None, False
            except Exception as e:
                self.__logger.error(f"Error downloading file '{file_path}' to local: {e}")
                return None, False
        else:
            local_file = file_path
            if not os.path.isfile(local_file):
                self.__logger.error(f"Local file {local_file} not found")
                return None, False
            
        return local_file, remove_local_file

    def get_s3_or_local_file_content(self, file_path: str):
        try:
            if file_path.startswith("s3://"):
                    content = self.s3_uri_get_object_content(file_path)
            elif os.path.isfile(file_path): # try to read the file locally
                with open(file_path, 'r') as file:
                    content = file.read()
            else: # try to get the object from this session's s3 bucket
                content = self.s3_get_object_content(file_path)
        except Exception as e:
            self.__logger.log_exception(f"Error reading file {file_path}: {e}")
            raise

        if not content:
            self.__logger.error(f"Failed to read file content from {file_path}")
            raise Exception(f"Failed to read file content from {file_path}")
        return content
    
    @staticmethod
    def s3_is_s3_uri(uri: str) -> bool:
        return uri.startswith("s3://")

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
    def s3_extract_bucket(s3_url):
        """Extract the bucket name from an S3 URL."""
        if s3_url.startswith("s3://"):
            # Remove the 's3://' prefix
            s3_url = s3_url[5:]
            # Find the first '/' after the bucket name
            key_start = s3_url.find('/')
            if key_start != -1:
                # Extract the bucket name
                return s3_url[:key_start]
        return None
    
    @staticmethod
    def s3_convert_https_url_to_s3_uri(https_url:str):
        parsed_url = urllib.parse.urlparse(https_url)

        # Example parsing: this may vary based on your S3 URL format.
        # For URLs like 'https://s3.amazonaws.com/bucket-name/path/to/file.json'
        parts = parsed_url.path.lstrip('/').split('/', 1)
        if len(parts) == 2:
            bucket, key = parts
            s3_uri = f"s3://{bucket}/{key}"
            return s3_uri
            # print("S3 URI:", s3_uri)
        else:
            raise ValueError(f"Could not parse bucket and key from the URL for {https_url}")
    
    
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
        match table_name:
            case 'speakers':
                return self.__speakers_table_name
            case _:
                return None
    
    def get_transcribe_client(self):
        return self.__transcribe  
    
    