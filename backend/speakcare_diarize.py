import os
import json
import time
import logging
import argparse
import numpy as np
from decimal import Decimal
from dotenv import load_dotenv
from datetime import datetime
from enum import Enum as PyEnum

import boto3
from botocore.exceptions import ClientError
from pydub import AudioSegment
from resemblyzer import VoiceEncoder, preprocess_wav
import warnings
from boto3_session import Boto3Session
from speakcare_logging import SpeakcareLogger
from speakcare_env import SpeakcareEnv
from os_utils import os_ensure_file_directory_exists, os_get_filename_without_ext, os_concat_current_time


warnings.filterwarnings("ignore", category=FutureWarning)

# Load environment variables and configure logging
if not load_dotenv("./.env"):
    print("No .env file found")
    exit(1)

SpeakcareEnv.prepare_env()

class SpeakerType(PyEnum):
    PATIENT = 'Patient'
    NURSE = 'Nurse'
    UNKNOWN = 'Unknown'


class TranscribeAndDiarize:
    def __init__(self):
        self.logger = SpeakcareLogger(__name__)
        self.b3session =  Boto3Session(SpeakcareEnv.get_working_dirs())
        self.init_env_variables()
        self.init_encoder()
        self.speakers_table_name = self.b3session.dynamo_get_table_name("speakers")

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

    def start_transcription_job(self, audio_key, bucket, job_name, output_filename=None):
        """Start AWS Transcribe job."""
        media_uri = f"s3://{bucket}/{audio_key}"
        _output_filename = output_filename if output_filename else f"{SpeakcareEnv.get_transcriptions_dir()}/{job_name}.json"
        response = self.b3session.get_transcribe_client().start_transcription_job(
            TranscriptionJobName=job_name,
            Media={"MediaFileUri": media_uri},
            MediaFormat="wav",
            LanguageCode="en-US",
            OutputBucketName=bucket,
            OutputKey=_output_filename,
            Settings={"ShowSpeakerLabels": True, "MaxSpeakerLabels": 10}
        )
        self.logger.info(f"Started transcription job: {job_name} into {output_filename}")
        return response

    def wait_for_transcription_job(self, job_name):
        """Wait for transcription job to complete."""
        waiting = 0
        while True:
            response = self.b3session.get_transcribe_client().get_transcription_job(TranscriptionJobName=job_name)
            status = response['TranscriptionJob']['TranscriptionJobStatus']
            
            if status == 'COMPLETED':
                s3Uri = Boto3Session.s3_convert_https_url_to_s3_uri(response['TranscriptionJob']['Transcript']['TranscriptFileUri'])
                self.logger.info(f"Transcription job completed. Output available in '{s3Uri}'")
                return response
            elif status == 'FAILED':
                raise RuntimeError(f"Transcription job failed: {response}")
            waiting +=1
            self.logger.debug(f"Waiting for transcription job to complete ({waiting})...")
            time.sleep(10)

    def get_s3_object_body(self, key):
        """Retrieve transcription output from S3."""
        return self.b3session.s3_get_object_body(key)

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


    def fetch_all_speakers(self):
        """Fetch all embeddings from a DynamoDB table."""
        table = self.b3session.dynamo_get_table(self.speakers_table_name)
        response = table.scan()
        return {item['Name']: item for item in response['Items']}
       
    
    def create_speaker(self, speaker_embedding, known_speakers, speaker_type: SpeakerType, speaker_name):
        """Match or create a new speaker in a specific table."""
        # Check for identical embeddings
        for known_speaker_name, speaker in known_speakers.items():
            embeddings = speaker.get('EmbeddingVectors', [])
            type = speaker.get('Type', '')
            for idx, known_embedding in enumerate(embeddings):
                embedding_vector = np.array(known_embedding, dtype=np.float32) 
                similarity = self.cosine_similarity(speaker_embedding, embedding_vector)
                if np.array_equal(speaker_embedding, embedding_vector):
                    self.logger.warning(f"Identical embedding found for speaker '{type}': '{known_speaker_name}' and new speaker '{speaker_type.value}': '{speaker_name}'. No changes made.")
                    return speaker, "identical"
                elif similarity >= self.addition_similarity_threshold and known_speaker_name != speaker_name:
                    self.logger.warning(f"High similarity found between new speaker {speaker_name} and existing speaker {known_speaker_name} with similarity {similarity}")

        # Add the new embedding to the speaker
        if speaker_name in known_speakers:
            speaker = self.add_embedding_to_speaker(speaker_name, speaker_embedding)
            self.logger.info(f"Added new embedding to existing speaker: {speaker_name}")
            return speaker, "added"
        else:
            speaker = self.add_new_speaker(speaker_name, speaker_embedding, speaker_type)
            self.logger.info(f"New speaker created: {speaker_name}")
            return speaker, "created"

    
    def match_or_create_speaker(self, speaker_embedding, known_speakers):
        """Match or create a new speaker in a specific table."""
        self.logger.debug(f"Matching or creating speaker embedding {len(speaker_embedding)} against known embeddings {len(known_speakers)}")
        best_match = None
        highest_similarity = -1
        for known_speaker_name, speaker in known_speakers.items():
            embeddings = speaker.get('EmbeddingVectors', [])
            type = speaker.get('Type', '')
            self.logger.debug(f"Checking speaker {known_speaker_name} embeddings {len(embeddings)}")
            for known_embedding in embeddings:
                self.logger.debug(f"Checking specific embedding {len(known_embedding)}")
                embedding_vector = np.array(known_embedding, dtype=np.float32)
                similarity = self.cosine_similarity(speaker_embedding, embedding_vector)
                self.logger.debug(f"cosine similarity: {similarity} with speaker {known_speaker_name}")
                if similarity >= self.matching_similarity_threshold:
                    self.logger.debug(f"Found high similarity: {similarity} with speaker {known_speaker_name}")
                    if similarity > highest_similarity:
                        best_match = speaker
                        highest_similarity = similarity

        if best_match:
            self.logger.debug(f"Match found: {best_match['Name']} with similarity {highest_similarity}")
            return best_match, "matched"
        else:
            self.logger.info(f"No match found. Creating new Unknown speaker")
            new_speaker_id = self.generate_unknown_speaker_id(known_speakers)
            return self.create_speaker(speaker_embedding, known_speakers, SpeakerType.UNKNOWN, new_speaker_id)
  

    def add_embedding_to_speaker(self, speaker_name, embedding):
        """Add a new embedding to an existing speaker."""
        embedding_decimal = [Decimal(str(value)) for value in embedding]
        table = self.b3session.dynamo_get_table(self.speakers_table_name)

        item = table.get_item(Key={'Name': speaker_name}).get('Item')
        if item:
            if 'EmbeddingVectors' not in item:
                item['EmbeddingVectors'] = [embedding_decimal]
            else:
                item['EmbeddingVectors'].append(embedding_decimal)
            table.put_item(Item=item)
            self.logger.info(f"Added new embedding to speaker {speaker_name} in table {self.speakers_table_name}")
            return item
        else:
            self.logger.error(f"Speaker {speaker_name} not found in table {self.speakers_table_name}")
            return None
        
 

    def add_new_speaker(self, speaker_name, embedding, speaker_type: SpeakerType):
        """Save speaker embedding to DynamoDB."""
        embedding_decimal = [Decimal(str(value)) for value in embedding]
        table = self.b3session.dynamo_get_table(self.speakers_table_name)
        item = {
            "EmbeddingVectors": [embedding_decimal],
            "Name": speaker_name,
            "Type": speaker_type.value,
            "Timestamp": datetime.now().isoformat()
        }
        table.put_item(Item=item)
        self.logger.info(f"Saved embedding for {speaker_name} in table {self.speakers_table_name}")
        return item


    def delete_embedding_from_dynamodb(self, speaker_name, embedding_index=None):
        """Delete speaker embedding from DynamoDB."""
        table = self.b3session.dynamo_get_table(self.speakers_table_name)
        try:
            if embedding_index is not None:
                item = table.get_item(Key={'Name': speaker_name}).get('Item')
                if item and 'EmbeddingVectors' in item:
                    del item['EmbeddingVectors'][embedding_index]
                    if item['EmbeddingVectors']:
                        table.put_item(Item=item)
                    else:
                        table.delete_item(Key={'Name': speaker_name})
                    self.logger.info(f"Deleted embedding index {embedding_index} for speaker {speaker_name} from table {self.speakers_table_name}")
            else:
                table.delete_item(Key={'Name': speaker_name})
                self.logger.info(f"Deleted item with Name {speaker_name} from table {self.speakers_table_name}")
        except ClientError as e:
            self.logger.error(f"Unable to delete item: {e.response['Error']['Message']}")


    def add_voice_sample(self, file_path, speaker_type: SpeakerType, speaker_name=None):
        """Process a voice sample and add to the specified table."""
        #remove white spaces from speaker_name and replace them witn _ (underscore)
        _speaker_name = speaker_name.replace(" ", "_") if speaker_name else None
        audio = AudioSegment.from_file(file_path)
        audio_data = np.array(audio.get_array_of_samples(), dtype=np.float32) / 32768.0
        
        wav = preprocess_wav(audio_data)
        embedding = self.encoder.embed_utterance(wav)
        
        all_speakers = self.fetch_all_speakers()
        speaker, result = self.create_speaker(embedding, all_speakers, speaker_type, speaker_name=_speaker_name)
        
        self.logger.info(f"add_voice_sample: create_speaker attepted for speaker '{speaker_type.value}': '{_speaker_name}'. Result: '{result}' with speaker '{speaker['Name']}'")

    @staticmethod
    def create_output_files_keys(output_file_prefix:str):
        """Create output file keys for transcription, diarization, and text."""                
        transcription_output_key = f"{SpeakcareEnv.get_transcriptions_dir()}/{output_file_prefix}-transcription.json"
        diarization_output_key = f"{SpeakcareEnv.get_diarizations_dir()}/{output_file_prefix}-diarization.json"
        text_output_key = f"{SpeakcareEnv.get_texts_dir()}/{output_file_prefix}-text.txt"
        
        return transcription_output_key, diarization_output_key, text_output_key


    def transcribe_and_recognize_speakers(self, audio_file: str, output_file_prefix: str='output'):
        """Main method to transcribe audio and recognize speakers."""

        transcription_output_key, diarization_output_key, text_output_key = self.create_output_files_keys(output_file_prefix)

        self.transcribe(audio_file, transcription_output_key)
        self.recognize_speakers(audio_file = audio_file, 
                                transcription_output_key=transcription_output_key,
                                diarization_output_key=diarization_output_key)
        
        return self.create_diarized_text(diarization_output_key=diarization_output_key, text_output_key=text_output_key)

    
    def transcribe(self, audio_file: str, transcription_output_key: str=None):
        """Main method to transcribe audio and recognize speakers."""

        # prepare output files
        output_time = int(time.time())
        transcription_job_name = f"transcription-{output_time}"

        audio_key = f"{SpeakcareEnv.get_audio_dir()}/{os.path.basename(audio_file)}"
        self.b3session.s3_upload_file(file_path=audio_file, key=audio_key)

        response = self.start_transcription_job(audio_key, self.b3session.s3_get_bucket_name(), transcription_job_name, transcription_output_key)
        self.logger.debug(f"Transcription start job response: {response}")
        self.wait_for_transcription_job(transcription_job_name)




    def recognize_speakers(self, audio_file: str, transcription_output_key: str, diarization_output_key: str):

        self.logger.info(f"recognize_speakers: transcription {transcription_output_key}. audio {audio_file}")
        transcription = self.get_s3_object_body(transcription_output_key)
        diarized_transcription = {}
        audio_segments = transcription['results']['audio_segments']
        segment_embeddings = self.extract_segment_embeddings(transcription, audio_file)

        all_speakers = self.fetch_all_speakers()

        # for segment, embedding in segment_embeddings.items():        
        self.logger.debug(f"transcribe_and_recognize_speaker: segment_embeddings {len(segment_embeddings)}")
        for index, segment in enumerate(segment_embeddings):
            self.logger.debug(f"Processing segment {index} slot {segment['slot']}")
            speaker, op = self.match_or_create_speaker(
                segment["embedding"], 
                all_speakers
            )
            diarized_transcription[index] = {
                "slot": segment["slot"], 
                "speaker": speaker['Name'],
                "role": speaker['Type'],
                "text": audio_segments[index]["transcript"]
            }
            # This is ugly but for now in case the op is "created" I want to add this embedding to the patients_embeddings so that the next segment can be matched with it
            if op == "created":
                all_speakers[speaker['Name']] = speaker
            
            self.logger.debug(f'Segment {index} slot: {segment["slot"]} {op} as {speaker}')
        
        self.logger.debug(f"Diarized transcription: {json.dumps(diarized_transcription, indent=4)}")
        
        # Write the diarized transcription to S3 into diariations folder
        self.b3session.s3_put_object(key=diarization_output_key, body=json.dumps(diarized_transcription))
        self.logger.info(f"Uploaded diarized transcription to 's3://{self.b3session.s3_get_bucket_name()}/{diarization_output_key}'")

    
    def create_diarized_text(self, diarization_output_key: str, text_output_key: str):

        self.logger.info(f"create_diarized_text: diarization {diarization_output_key}.")
        # write the free text of the diarized transcription. Every line strats with "<Speaker label>: " and the speaker name and then the text
        # put it in s3 under the texts folder
        diarized_transcription = self.b3session.s3_get_object_body(diarization_output_key)
       
        temp_file = f"{SpeakcareEnv.get_texts_local_dir()}/{text_output_key}"
        # make sure the file dirs exist
        os_ensure_file_directory_exists(temp_file)
        # os.makedirs(os.path.dirname(temp_file), exist_ok=True)
        with open(temp_file, "w") as f:
            for segment in diarized_transcription.values():
                f.write(f"{segment['role']} {segment['speaker']}: {segment['text']}\n")
        self.b3session.s3_upload_file(file_path=temp_file, key=text_output_key)
        self.logger.info(f"Uploaded text transcription to s3://{self.b3session.s3_get_bucket_name()}/{text_output_key}")
        os.remove(temp_file)

        return text_output_key
    

def main():
    parser = argparse.ArgumentParser(description="Speaker Recognition Tool")
    choices = ["full", "transcribe", "diarize"]
    parser.add_argument(
        '-f', '--function',
        type=str, 
        choices=choices, 
        required=True, 
        help=f"Function: {choices}"
    )
    parser.add_argument('-a', '--audio', type=str, required=True, help="Local path to audio file.")
    parser.add_argument('-i', '--input', type=str, help="S3 path to the specific input text file.")
    args = parser.parse_args()

    transcriber = TranscribeAndDiarize()

    audio_file = args.audio
    input_file_path = args.input
    # input_file_prefix = os_get_filename_without_ext(input_file_path) if input_file_path else None
    audio_prefix = os_concat_current_time(os_get_filename_without_ext(audio_file)) if audio_file else None

    match args.function:
        case "full":
            if not audio_file:
                print("Audio file is required for full operation")
                exit(1)
            transcriber.transcribe_and_recognize_speakers(audio_file, audio_prefix)

        case "transcribe":
            if not audio_file:
                print("Audio is required for transcription")
                exit(2)
            transcription, _, _ = transcriber.create_output_files_keys(audio_prefix)
            transcriber.transcribe(audio_file, transcription)

        case "diarize":
            if not audio_file or not input_file_path:
                print("Audio and input file are required for diarization")
                exit(3)
            # The input file is a post recognition file
            _, diarization, text = transcriber.create_output_files_keys(audio_prefix)
            transcriber.recognize_speakers(audio_file=audio_file, 
                                           transcription_output_key=Boto3Session.s3_extract_key(input_file_path), # this is the input file
                                           diarization_output_key=diarization)
            transcriber.create_diarized_text(diarization_output_key=diarization,
                                             text_output_key=text)
        case _:
            print(f"Invalid function '{args.function}'")
            exit(1)

if __name__ == "__main__":
    main()