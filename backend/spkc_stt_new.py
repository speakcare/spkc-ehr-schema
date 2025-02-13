import os
import json
import time
import logging
import argparse
import numpy as np
from decimal import Decimal
from dotenv import load_dotenv
from datetime import datetime

import boto3
from botocore.exceptions import ClientError
from pydub import AudioSegment
from resemblyzer import VoiceEncoder, preprocess_wav
import warnings


warnings.filterwarnings("ignore", category=FutureWarning)

# Load environment variables and configure logging
load_dotenv("./.env.app")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SpeakerRecognition:
    

    def __init__(self):
        self.init_env_variables()
        self.init_boto3_clients()
        self.init_s3_bucket()
        self.init_dynamodb_tables()
        self.init_encoder()

    

    def init_env_variables(self):
        # Configuration from environment variables
        self.profile_name = os.getenv("AWS_PROFILE", "default")
        self.s3_bucket_name = os.getenv("S3_BUKET_NAME", "speakcare-pilot")
        self.output_table_name = os.getenv("DYNAMODB_TABLE_NAME", "SpeakerEmbeddings")
        self.nurses_table_name = os.getenv("NURSES_TABLE_NAME", "Nurses")
        self.patients_table_name = os.getenv("PATIENTS_TABLE_NAME", "Patients")
        self.dynamodb_table_names = [self.nurses_table_name, self.patients_table_name] # list to iterate over table names
        self.similarity_threshold = float(os.getenv("SIMILARITY_THRESHOLD", 0.7))
        self.running_local = os.getenv("RUNNING_LOCAL", "False").lower() == "true"
        self.localstack_endpoint = os.getenv("LOCALSTACK_ENDPOINT", "http://localhost:4566")


    def init_boto3_clients(self):
        
        if self.running_local:
            logger.info("Initializing clients for LocalStack...")
        else:
            logger.info("Initializing clients for AWS...") 
        
        endpoint_url = self.localstack_endpoint if self.running_local else None
        self.session = boto3.Session(profile_name=self.profile_name)  # No profile needed for LocalStack
        logger.info(f"AWS region: {self.session.region_name}")

        # Configure clients to use LocalStack
        self.s3_client = self.session.client('s3', endpoint_url=endpoint_url)
        self.transcribe = self.session.client('transcribe', region_name=self.session.region_name)
        self.dynamodb = self.session.resource('dynamodb', endpoint_url=endpoint_url)

        # Example: List buckets in LocalStack
        self.buckets = self.s3_client.list_buckets()
        logger.info(f"S3 Buckets: {[bucket['Name'] for bucket in self.buckets.get('Buckets', [])]}")


    def init_s3_bucket(self):
        # Create a new bucket
        # check if the bucket already exists
        bucket_exists = False
        for bucket in self.s3_client.list_buckets()['Buckets']:
            if bucket['Name'] == self.s3_bucket_name:
                bucket_exists = True
                break
        if not bucket_exists:
            self.s3_client.create_bucket(Bucket=self.s3_bucket_name)
            # creat directories
            self.s3_client.put_object(Bucket=self.s3_bucket_name, Key="audio/")
            self.s3_client.put_object(Bucket=self.s3_bucket_name, Key="transcriptions/")
            self.s3_client.put_object(Bucket=self.s3_bucket_name, Key="diarizations/")
            self.s3_client.put_object(Bucket=self.s3_bucket_name, Key="texts/")
            self.s3_client.put_object(Bucket=self.s3_bucket_name, Key="wavs/")
            logger.info(f"Created S3 bucket: {self.s3_bucket_name}")

    def init_dynamodb_tables(self):
        # Create a new table
        table_exists = False
        allTables = self.dynamodb.tables.all()
        existing_table_names = [table.name for table in allTables]
        logger.info(f"init_dynamodb_tables {self.dynamodb_table_names}: Found existing tables: {[table.name for table in allTables]}")
        for tableName in self.dynamodb_table_names:
            logger.info(f"Checking if table '{tableName}' exists")
            if tableName in existing_table_names:
                logger.info(f"DynamoDB table '{tableName}' already exists")
                continue
            else:
                table = self.dynamodb.create_table(
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
                logger.info(f"Created DynamoDB table: '{tableName}'")
        logger.info(f"DynamoDB done creating tables")

    
        # Initialize Resemblyzer
    def init_encoder(self):
        self.encoder = VoiceEncoder()

    def upload_audio_to_s3(self, audio_path, bucket, key):
        """Upload audio file to S3."""
        with open(audio_path, "rb") as f:
            self.s3_client.upload_fileobj(f, bucket, key)
        logger.info(f"Uploaded {audio_path} to s3://{bucket}/{key}")

    def start_transcription_job(self, audio_key, bucket, job_name):
        """Start AWS Transcribe job."""
        media_uri = f"s3://{bucket}/{audio_key}"
        response = self.transcribe.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={"MediaFileUri": media_uri},
            MediaFormat="wav",
            LanguageCode="en-US",
            OutputBucketName=bucket,
            OutputKey=f"transcriptions/{job_name}.json",
            Settings={"ShowSpeakerLabels": True, "MaxSpeakerLabels": 10}
        )
        logger.info(f"Started transcription job: {job_name}")
        return response

    def wait_for_transcription_job(self, job_name):
        """Wait for transcription job to complete."""
        while True:
            response = self.transcribe.get_transcription_job(TranscriptionJobName=job_name)
            status = response['TranscriptionJob']['TranscriptionJobStatus']
            
            if status == 'COMPLETED':
                logger.info("Transcription job completed.")
                return response
            elif status == 'FAILED':
                raise RuntimeError(f"Transcription job failed: {response}")
            
            logger.info("Waiting for transcription job to complete...")
            time.sleep(10)

    def get_transcription_output(self, bucket, key):
        """Retrieve transcription output from S3."""
        obj = self.s3_client.get_object(Bucket=bucket, Key=key)
        return json.loads(obj['Body'].read())

    def extract_segment_embeddings(self, transcription, audio_path):
        """Extract speaker embeddings from audio."""
        audio = AudioSegment.from_file(audio_path)
        segments = transcription['results']['speaker_labels']['segments']
        segment_embeddings = []
        
        for segment in segments:
            # take the infrom the transcription
            start_time = float(segment['start_time']) * 1000
            end_time = float(segment['end_time']) * 1000
            
            audio_segment = audio[start_time:end_time]
            # get as numpy array and normalize to 16 bits
            audio_data = np.array(audio_segment.get_array_of_samples(), dtype=np.float32) / 32768.0
            
            wav = preprocess_wav(audio_data)
            embedding = self.encoder.embed_utterance(wav)
            slot = f"{start_time}:{end_time}"
            segment_info = {"slot": slot, "embedding": embedding}
            segment_embeddings.append(segment_info)
        
        return segment_embeddings

    def fetch_all_embeddings(self, table_name):
        """Fetch all embeddings from a DynamoDB table."""
        table = self.dynamodb.Table(table_name)
        response = table.scan()
        return {item['Name']: np.array(item['EmbeddingVector'], dtype=np.float32) 
                for item in response['Items']}
    
    def generate_unknown_speaker_id(self, known_embeddings):
        """Generate a new unknown speaker ID."""
        unknown_prefix = "Unknown-"
        unknown_ids = [key for key in known_embeddings.keys() if key.startswith(unknown_prefix)]
        
        if not unknown_ids:
            return f"{unknown_prefix}0"
        
        max_id = max(int(key.split('-')[1]) for key in unknown_ids)
        return f"{unknown_prefix}{max_id + 1}"

    @staticmethod
    def cosine_similarity(vec1, vec2):
        """Calculate cosine similarity between two vectors."""
        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

    def create_speaker(self, embedding, known_embeddings, table_name, speaker_name):
        """Match or create a new speaker in a specific table."""
        best_match = None
        highest_similarity = -1
        for speaker_id, known_embedding in known_embeddings.items():
            similarity = self.cosine_similarity(embedding, known_embedding)
            if (similarity > highest_similarity and similarity >= self.similarity_threshold):
                best_match = speaker_id
                highest_similarity = similarity

        if best_match:
            logger.info(f"Match found: {best_match} with similarity {similarity}")
            logger.info(f"Replacing embedding for {best_match} with new {speaker_name} in table {table_name}")
            self.delete_embedding_from_dynamodb(best_match, table_name)
            self.save_embedding_to_dynamodb(speaker_name, embedding, table_name)
            return speaker_name, "replaced"
        else:
            self.save_embedding_to_dynamodb(speaker_name, embedding, table_name)
            logger.info(f"New speaker created: {speaker_name}")
            return speaker_name, "created"


    def match_or_create_speaker(self, embedding, known_embeddings, table_name):
        """Match or create a new speaker in a specific table."""
        best_match = None
        highest_similarity = -1
        for speaker_id, known_embedding in known_embeddings.items():
            similarity = self.cosine_similarity(embedding, known_embedding)
            logger.info(f"Found similarity: {similarity} with speaker {speaker_id}")
            if (similarity > highest_similarity and similarity >= self.similarity_threshold):
                best_match = speaker_id
                highest_similarity = similarity

        if best_match:
            logger.info(f"Match found: {best_match} with similarity {similarity}")
            return best_match, "matched"
        else:
            new_speaker_id = self.generate_unknown_speaker_id(known_embeddings)
            return self.create_speaker(embedding, known_embeddings, table_name, new_speaker_id)

    def save_embedding_to_dynamodb(self, speaker_id, embedding, table_name):
        """Save speaker embedding to DynamoDB."""
        embedding_decimal = [Decimal(str(value)) for value in embedding]
        table = self.dynamodb.Table(table_name)

        item = {
            "EmbeddingVector": embedding_decimal,
            "Name": speaker_id,
            "Type": table_name.rstrip('s'),
            "Timestamp": datetime.now().isoformat()
        }
        
        table.put_item(Item=item)
        logger.info(f"Saved embedding for {speaker_id} in table {table_name}")

    def delete_embedding_from_dynamodb(self, speaker_id, table_name):
        """Delete speaker embedding to DynamoDB."""
        table = self.dynamodb.Table(table_name)
        try:
            table.delete_item(
                Key={
                    'Name': speaker_id
                }
            )
            logger.info(f"Deleted item with Name {speaker_id} from table {table_name}")
        except ClientError as e:
            logger.error(f"Unable to delete item: {e.response['Error']['Message']}")


    def add_voice_sample(self, file_path, table_name, speaker_name=None):
        """Process a voice sample and add to the specified table."""
        audio = AudioSegment.from_file(file_path)
        audio_data = np.array(audio.get_array_of_samples(), dtype=np.float32) / 32768.0
        
        wav = preprocess_wav(audio_data)
        embedding = self.encoder.embed_utterance(wav)
        
        known_embeddings = self.fetch_all_embeddings(table_name)
        self.create_speaker(embedding, known_embeddings, table_name, speaker_name=speaker_name)
        
        logger.info(f"Voice sample processed and saved to table {table_name}")



    def transcribe_and_recognize_speakers(self, audio_file):
        """Main method to transcribe audio and recognize speakers."""
        audio_key = f"audio/{os.path.basename(audio_file)}"
        self.upload_audio_to_s3(audio_file, self.s3_bucket_name, audio_key)

        output_time = int(time.time())
        transcription_job_name = f"transcription-{output_time}"
        self.start_transcription_job(audio_key, self.s3_bucket_name, transcription_job_name)
        self.wait_for_transcription_job(transcription_job_name)

        transcription_output_key = f"transcriptions/{transcription_job_name}.json"
        transcription = self.get_transcription_output(self.s3_bucket_name, transcription_output_key)

        diarized_transcription = {}# transcription['results']['speaker_labels']
        audio_segments = transcription['results']['audio_segments']
        segment_embeddings = self.extract_segment_embeddings(transcription, audio_file)

        patients_embeddings = self.fetch_all_embeddings("Patients")
        nurses_embeddings = self.fetch_all_embeddings("Nurses")

        # for segment, embedding in segment_embeddings.items():        
        for index, segment in enumerate(segment_embeddings):
            logger.info(f"Processing segment {index} slot {segment['slot']}")
            speaker_id, op = self.match_or_create_speaker(
                segment["embedding"], 
                {**patients_embeddings, **nurses_embeddings}, 
                "Patients"  # Default table for new speakers
            )
            diarized_transcription[index] = {
                "slot": segment["slot"], 
                "speaker": speaker_id,
                "text": audio_segments[index]["transcript"]
            }
            # This is ugly but for now in case the op is "created" I want to add this embedding to the patients_embeddings so that the next segment can be matched with it
            if op == "created":
                patients_embeddings[speaker_id] = segment["embedding"]
            
            logger.info(f"Segment {index} slot: {segment["slot"]} {op} as {speaker_id}")
        
        logger.info(f"Diarized transcription: {json.dumps(diarized_transcription, indent=4)}")
        # Write the diarized transcription to S3 into diariations folder
        diarization_output_key = f"diarizations/diarization-{output_time}.json"
        self.s3_client.put_object(Bucket=self.s3_bucket_name, Key=diarization_output_key, Body=json.dumps(diarized_transcription))
        logger.info(f"Uploaded diarized transcription to s3://{self.s3_bucket_name}/{diarization_output_key}")
        # write the free text of the diarized transcription. Every line strats with "<Speaker label>: " and the speaker name and then the text
        # put it in s3 under the texts folder
        text_output_key = f"texts/text-{output_time}.txt"
        temp_file = f"/tmp/{text_output_key}"
        # make sure the file dirs exist
        os.makedirs(os.path.dirname(temp_file), exist_ok=True)
        with open(temp_file, "w") as f:
            for segment in diarized_transcription.values():
                f.write(f"{segment['speaker']}: {segment['text']}\n")
        self.s3_client.upload_file(f"/tmp/{text_output_key}", self.s3_bucket_name, text_output_key)
        logger.info(f"Uploaded text transcription to s3://{self.s3_bucket_name}/{text_output_key}")

def main():
    parser = argparse.ArgumentParser(description="Speaker Recognition Tool")
    parser.add_argument(
        "--mode", 
        type=str, 
        choices=["transcribe", "add_patient", "add_nurse"], 
        required=True, 
        help="Operation mode: transcribe, add_patient, or add_nurse."
    )
    parser.add_argument("--speaker", type=str, required=False, help="Name of the speaker.")
    parser.add_argument("--file", type=str, required=True, help="Path to the audio file.")
    args = parser.parse_args()

    speaker_recognition = SpeakerRecognition()

    speaker = args.speaker if args.speaker else None

    if args.mode == "transcribe":
        speaker_recognition.transcribe_and_recognize_speakers(args.file)
    elif args.mode == "add_patient":
        speaker_recognition.add_voice_sample(file_path = args.file, table_name = speaker_recognition.patients_table_name, speaker_name=speaker)
    elif args.mode == "add_nurse":
        speaker_recognition.add_voice_sample(file_path = args.file, table_name = speaker_recognition.nurses_table_name, speaker_name=speaker)

if __name__ == "__main__":
    main()