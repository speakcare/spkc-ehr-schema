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
from boto3_session import Boto3Session
from speakcare_logging import SpeakcareLogger


warnings.filterwarnings("ignore", category=FutureWarning)

# Load environment variables and configure logging
if not load_dotenv("./.env"):
    print("No .env file found")
    exit(1)
else:
    print("Loaded .env file")
    print (f"AIRTABLE_API_KEY: {os.getenv('AIRTABLE_API_KEY')}")

# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

s3dirs: list = ["audio", "transcriptions", "diarizations", "texts", "wavs"]

class TranscribeAndDiarize:
    def __init__(self):
        self.logger = SpeakcareLogger(__name__)
        self.b3session =  Boto3Session(s3dirs)
        self.init_env_variables()
        self.init_encoder()

    def init_env_variables(self):
        # Configuration from environment variables
        self.matching_similarity_threshold = float(os.getenv("MATCHING_SIMILARITY_THRESHOLD", 0.75))
        self.addition_similarity_threshold = float(os.getenv("ADDITION_SIMILARITY_THRESHOLD", 0.95))

        # Initialize Resemblyzer
    def init_encoder(self):
        self.encoder = VoiceEncoder()

    def upload_audio_to_s3(self, audio_path, key):
        """Upload audio file to S3."""
        with open(audio_path, "rb") as f:
            self.b3session.s3_upload_file_obj(f, key)
            # self.s3_client.upload_fileobj(f, bucket, key)

    def start_transcription_job(self, audio_key, bucket, job_name):
        """Start AWS Transcribe job."""
        media_uri = f"s3://{bucket}/{audio_key}"
        response = self.b3session.get_transcribe_client().start_transcription_job(
            TranscriptionJobName=job_name,
            Media={"MediaFileUri": media_uri},
            MediaFormat="wav",
            LanguageCode="en-US",
            OutputBucketName=bucket,
            OutputKey=f"transcriptions/{job_name}.json",
            Settings={"ShowSpeakerLabels": True, "MaxSpeakerLabels": 10}
        )
        self.logger.info(f"Started transcription job: {job_name}")
        return response

    def wait_for_transcription_job(self, job_name):
        """Wait for transcription job to complete."""
        waiting = 0
        while True:
            response = self.b3session.get_transcribe_client().get_transcription_job(TranscriptionJobName=job_name)
            status = response['TranscriptionJob']['TranscriptionJobStatus']
            
            if status == 'COMPLETED':
                self.logger.info("Transcription job completed.")
                return response
            elif status == 'FAILED':
                raise RuntimeError(f"Transcription job failed: {response}")
            waiting +=1
            self.logger.info(f"Waiting for transcription job to complete ({waiting})...")
            time.sleep(10)

    def get_transcription_output(self, key):
        """Retrieve transcription output from S3."""
        obj = self.b3session.s3_get_object(key=key)
        # obj = self.s3_client.get_object(Bucket=bucket, Key=key)
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


    def fetch_all_embeddings(self, table_name):
        """Fetch all embeddings from a DynamoDB table."""
        table = self.b3session.dynamo_get_table(table_name)
        response = table.scan()
        return {item['Name']: [np.array(vec, dtype=np.float32) for vec in item.get('EmbeddingVectors', [])] 
            for item in response['Items']}
       
    
    def create_speaker(self, embedding, known_embeddings, table_name, speaker_name):
        """Match or create a new speaker in a specific table."""
        # Check for identical embeddings
        for speaker_id, embeddings in known_embeddings.items():
            for idx, known_embedding in enumerate(embeddings):
                similarity = self.cosine_similarity(embedding, known_embedding)
                if np.array_equal(embedding, known_embedding):
                    self.logger.warning(f"Identical embedding found for speaker {speaker_id} and new speaker {speaker_name}. No changes made.")
                    return speaker_id, "identical"
                elif similarity >= self.addition_similarity_threshold and speaker_id != speaker_name:
                    self.logger.warning(f"High similarity found between new speaker {speaker_name} and existing speaker {speaker_id} with similarity {similarity}")

        # Add the new embedding to the speaker
        if speaker_name in known_embeddings:
            self.add_embedding_to_speaker(speaker_name, embedding, table_name)
            self.logger.info(f"Added new embedding to existing speaker: {speaker_name}")
            return speaker_name, "added"
        else:
            self.add_new_speaker(speaker_name, embedding, table_name)
            self.logger.info(f"New speaker created: {speaker_name}")
            return speaker_name, "created"

    
    def add_embedding_to_speaker(self, speaker_name, embedding, table_name):
        """Add a new embedding to an existing speaker."""
        embedding_decimal = [Decimal(str(value)) for value in embedding]
        table = self.b3session.dynamo_get_table(table_name)

        item = table.get_item(Key={'Name': speaker_name}).get('Item')
        if item:
            if 'EmbeddingVectors' not in item:
                item['EmbeddingVectors'] = [embedding_decimal]
            else:
                item['EmbeddingVectors'].append(embedding_decimal)
            table.put_item(Item=item)
            self.logger.info(f"Added new embedding to speaker {speaker_name} in table {table_name}")
        else:
            self.logger.error(f"Speaker {speaker_name} not found in table {table_name}")
        
    def match_or_create_speaker(self, embedding, known_embeddings, table_name):
        """Match or create a new speaker in a specific table."""
        self.logger.debug(f"Matching or creating speaker embedding {len(embedding)} against known embeddings {len(known_embeddings)}")
        best_match = None
        highest_similarity = -1
        for speaker_id, embeddings in known_embeddings.items():
            self.logger.debug(f"Checking speaker {speaker_id} embeddings {len(embeddings)}")
            for known_embedding in embeddings:
                self.logger.debug(f"Checking specific embedding {len(known_embedding)}")
                similarity = self.cosine_similarity(embedding, known_embedding)
                self.logger.debug(f"cosine similarity: {similarity} with speaker {speaker_id}")
                if similarity >= self.matching_similarity_threshold:
                    self.logger.info(f"Found high similarity: {similarity} with speaker {speaker_id}")
                    if similarity > highest_similarity:
                        best_match = speaker_id
                        highest_similarity = similarity

        if best_match:
            self.logger.info(f"Match found: {best_match} with similarity {highest_similarity}")
            return best_match, "matched"
        else:
            self.logger.info(f"No match found. Creating new Unknown speaker")
            new_speaker_id = self.generate_unknown_speaker_id(known_embeddings)
            return self.create_speaker(embedding, known_embeddings, table_name, new_speaker_id)


    def add_new_speaker(self, speaker_id, embedding, table_name):
        """Save speaker embedding to DynamoDB."""
        embedding_decimal = [Decimal(str(value)) for value in embedding]
        table = self.b3session.dynamo_get_table(table_name)
        item = {
            "EmbeddingVectors": [embedding_decimal],
            "Name": speaker_id,
            "Type": table_name.rstrip('s'),
            "Timestamp": datetime.now().isoformat()
        }
        table.put_item(Item=item)
        self.logger.info(f"Saved embedding for {speaker_id} in table {table_name}")


    def delete_embedding_from_dynamodb(self, speaker_id, table_name, embedding_index=None):
        """Delete speaker embedding from DynamoDB."""
        table = self.b3session.dynamo_get_table(table_name)
        try:
            if embedding_index is not None:
                item = table.get_item(Key={'Name': speaker_id}).get('Item')
                if item and 'EmbeddingVectors' in item:
                    del item['EmbeddingVectors'][embedding_index]
                    if item['EmbeddingVectors']:
                        table.put_item(Item=item)
                    else:
                        table.delete_item(Key={'Name': speaker_id})
                    self.logger.info(f"Deleted embedding index {embedding_index} for speaker {speaker_id} from table {table_name}")
            else:
                table.delete_item(Key={'Name': speaker_id})
                self.logger.info(f"Deleted item with Name {speaker_id} from table {table_name}")
        except ClientError as e:
            self.logger.error(f"Unable to delete item: {e.response['Error']['Message']}")


    def add_voice_sample(self, file_path, table_name, speaker_name=None):
        """Process a voice sample and add to the specified table."""
        audio = AudioSegment.from_file(file_path)
        audio_data = np.array(audio.get_array_of_samples(), dtype=np.float32) / 32768.0
        
        wav = preprocess_wav(audio_data)
        embedding = self.encoder.embed_utterance(wav)
        
        known_embeddings = self.fetch_all_embeddings(table_name)
        speaker, result = self.create_speaker(embedding, known_embeddings, table_name, speaker_name=speaker_name)
        
        self.logger.info(f"add_voice_sample: create_speaker attepted to table '{table_name}' for speaker '{speaker_name}'. Result: '{result}' with speaker '{speaker}'")



    def transcribe_and_recognize_speakers(self, audio_file):
        """Main method to transcribe audio and recognize speakers."""
        audio_key = f"audio/{os.path.basename(audio_file)}"
        self.b3session.s3_upload_file(file_path=audio_file, key=audio_key)

        output_time = int(time.time())
        transcription_job_name = f"transcription-{output_time}"
        self.start_transcription_job(audio_key, self.b3session.s3_get_bucket_name(), transcription_job_name)
        self.wait_for_transcription_job(transcription_job_name)

        transcription_output_key = f"transcriptions/{transcription_job_name}.json"
        transcription = self.get_transcription_output(transcription_output_key)

        diarized_transcription = {}# transcription['results']['speaker_labels']
        audio_segments = transcription['results']['audio_segments']
        segment_embeddings = self.extract_segment_embeddings(transcription, audio_file)

        patients_embeddings = self.fetch_all_embeddings("Patients")
        nurses_embeddings = self.fetch_all_embeddings("Nurses")

        # for segment, embedding in segment_embeddings.items():        
        self.logger.debug(f"transcribe_and_recognize_speaker: segment_embeddings {len(segment_embeddings)}")
        for index, segment in enumerate(segment_embeddings):
            self.logger.debug(f"Processing segment {index} slot {segment['slot']}")
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
                patients_embeddings[speaker_id] = [segment["embedding"]]
            
            self.logger.debug(f'Segment {index} slot: {segment["slot"]} {op} as {speaker_id}')
        
        self.logger.debug(f"Diarized transcription: {json.dumps(diarized_transcription, indent=4)}")
        # Write the diarized transcription to S3 into diariations folder
        diarization_output_key = f"diarizations/diarization-{output_time}.json"
        self.b3session.s3_put_object(key=diarization_output_key, body=json.dumps(diarized_transcription))
        self.logger.info(f"Uploaded diarized transcription to s3://{self.b3session.s3_get_bucket_name()}/{diarization_output_key}")
        # write the free text of the diarized transcription. Every line strats with "<Speaker label>: " and the speaker name and then the text
        # put it in s3 under the texts folder
        text_output_key = f"texts/text-{output_time}.txt"
        temp_file = f"/tmp/{text_output_key}"
        # make sure the file dirs exist
        os.makedirs(os.path.dirname(temp_file), exist_ok=True)
        with open(temp_file, "w") as f:
            for segment in diarized_transcription.values():
                f.write(f"{segment['speaker']}: {segment['text']}\n")
        self.b3session.s3_upload_file(file_path=temp_file, key=text_output_key)
        self.logger.info(f"Uploaded text transcription to s3://{self.b3session.s3_get_bucket_name()}/{text_output_key}")

        return text_output_key
    
    def get_nurses_table_name(self):
        return self.b3session

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

    transcriber = TranscribeAndDiarize()

    speaker = args.speaker if args.speaker else None

    if args.mode == "transcribe":
        transcriber.transcribe_and_recognize_speakers(args.file)
    elif args.mode == "add_patient":
        transcriber.add_voice_sample(file_path = args.file, table_name = transcriber.b3session.dynamo_get_table_name("patients"), speaker_name=speaker)
    elif args.mode == "add_nurse":
        transcriber.add_voice_sample(file_path = args.file, table_name = transcriber.b3session.dynamo_get_table_name("nurses"), speaker_name=speaker)

if __name__ == "__main__":
    main()