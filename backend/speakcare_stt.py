from abc import ABC, abstractmethod
import time
import openai
from openai import OpenAI
import argparse
from dotenv import load_dotenv
from datetime import datetime, timezone
import os
from speakcare_audio import audio_record, audio_is_wav, audio_convert_to_wav
from speakcare_logging import SpeakcareLogger
from boto3_session import Boto3Session
from speakcare_env import SpeakcareEnv
from os_utils import os_sanitize_name

load_dotenv()
logger = SpeakcareLogger(__name__)

# Set your OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")


class SpeakcareSTT(ABC):

    def __init__(self):
        pass

    @abstractmethod
    def transcribe(self, audio_file: str, transcription_output_file: str=None):
        raise NotImplementedError()


class SpeakcareOpenAIWhisper(SpeakcareSTT):
    def __init__(self):
        super().__init__()
        self.client = OpenAI()
        self.logger = SpeakcareLogger(SpeakcareOpenAIWhisper.__name__)
        self.b3session = Boto3Session.get_single_instance()

    def transcribe(self, audio_file="input.wav", transcription_output_file="transcipt.txt", append=False):


        transcript = None
        self.client = OpenAI()
        audio_file, remove_local_file = self.b3session.s3_localize_file(audio_file)
        write_mode = "a" if append else "w"
        try:
            with open(audio_file, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(model="whisper-1", file=audio_file)

            # write the transcript to a text file
            self.logger.debug(f"Opening transcription output file {transcription_output_file} in {write_mode} mode")
            with open(transcription_output_file, write_mode) as text_file:
                text_file.write(transcript.text)
        except Exception as e:
            self.logger.log_exception("Error transcribing audio", e)
            return 0
        finally:
            if remove_local_file:
                os.remove(audio_file)

        transcription_length= len(transcript.text)
        self.logger.info(f"Transcription saved to {transcription_output_file} length: {transcription_length} characters")
        return transcription_length



class SpeakcareAWSTranscribe(SpeakcareSTT):
    def __init__(self):
        super().__init__()
        self.logger = SpeakcareLogger(SpeakcareAWSTranscribe.__name__)
        self.b3session = Boto3Session.get_single_instance()
        self.wait_sleep = 10

    def transcribe(self, audio_file: str, transcription_output_file: str=None):
        """Main method to transcribe audio and recognize speakers."""

        if self.b3session.s3_is_s3_uri(transcription_output_file): #.startswith("s3://"):
            transcription_output_key = boto3Session.s3_extract_key(transcription_output_file)
        else:
            transcription_output_key = transcription_output_file

        # If S3 file use it as is, otherwise upload to S3
        if not self.b3session.s3_is_s3_uri(audio_file): #.startswith("s3://"):
            audio_key = f"{SpeakcareEnv.get_audio_dir()}/{os.path.basename(audio_file)}"
            try:
                self.b3session.s3_upload_file(file_path=audio_file, key=audio_key)

                audio_uri = self.b3session.s3_get_file_uri(audio_key)
            except Exception as e:
                self.logger.log_exception("Error uploading audio to S3", e)
                return 0
        else:
            audio_uri = audio_file
            self.logger.debug(f"Using S3 audio file: {audio_uri}")

        # prepare output files
        output_time = int(time.time())
        transcription_job_name = f"transcription-{output_time}"



        try:

            response = self.__start_transcription_job(audio_uri= audio_uri, output_bucket= self.b3session.s3_get_bucket_name(), 
                                                      job_name= transcription_job_name, output_filename= transcription_output_key)
            self.logger.debug(f"Transcription start job response: {response}")
            self.__wait_for_transcription_job(transcription_job_name)
            return self.b3session.s3_get_object_size(transcription_output_key)
        except Exception as e:
            self.logger.log_exception("Error transcribing audio", e)
            return 0

    def __start_transcription_job(self, audio_uri, output_bucket, job_name, output_filename=None):
        """Start AWS Transcribe job."""
        _output_filename = output_filename if output_filename else f"{SpeakcareEnv.get_transcriptions_dir()}/{job_name}.json"
        response = self.b3session.get_transcribe_client().start_transcription_job(
            TranscriptionJobName=job_name,
            Media={"MediaFileUri": audio_uri},
            MediaFormat="wav",
            LanguageCode="en-US",
            OutputBucketName=output_bucket,
            OutputKey=_output_filename,
            Settings={"ShowSpeakerLabels": True, "MaxSpeakerLabels": 10}
        )
        self.logger.info(f"Started transcription job: {job_name} into {output_filename}")
        return response

    def __wait_for_transcription_job(self, job_name):
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
            time.sleep(self.wait_sleep)

    



def record_and_transcribe():
    # Step 1: Record Audio
    audio_filename = "input.wav"
    audio_record(duration=5, output_filename=audio_filename)

    # Step 2: Transcribe Audio
    stt = SpeakcareOpenAIWhisper()
    transcription = stt.transcribe(audio_file=audio_filename)
    print("Transcription:", transcription)

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Speakcare speech to text.')
    parser.add_argument('-o', '--output', type=str, default="output", help='Output file prefix (default: output)')
    parser.add_argument('-i', '--input', type=str, required=True, help='Input file name (default: input)')
    parser.add_argument('-m', '--model', type=str, 
                        choices=['openai','aws'], default='openai', help='Model: openai (whisper) or aws (default: openai)')

    args = parser.parse_args()

    SpeakcareEnv.load_env()

    input_file = args.input
    output_file_prefix = args.output

    # Get the current UTC time
    utc_now = datetime.now(timezone.utc)

    # Format the datetime as a string without microseconds and timezone
    utc_string = utc_now.strftime('%Y-%m-%dT%H-%M-%S')
    output_filename = os_sanitize_name(f'{output_file_prefix}.{utc_string}')
    boto3Session = Boto3Session.get_single_instance()

    local_audio_file, remove_local_file = boto3Session.s3_localize_file(input_file)
    wav_filename = None
    if not audio_is_wav(local_audio_file):
        wav_filename = audio_convert_to_wav(local_audio_file)
        input_file = wav_filename
    else:
        input_file = local_audio_file

    if args.model == 'aws':
        boto3Session = Boto3Session.get_single_instance()
        output_path = f'{SpeakcareEnv.get_transcriptions_dir()}/{output_filename}.json'
        stt = SpeakcareAWSTranscribe()
        logger.info(f"AWS tanscribing audio from {input_file} into {output_path}")
        stt.transcribe(audio_file=input_file, transcription_output_file=output_path)
    else:
        output_path = f'{SpeakcareEnv.get_texts_local_dir()}/{output_filename}.txt'
        logger.info(f"Whisper transcribing audio from {input_file} into {output_path}")
        stt = SpeakcareOpenAIWhisper()
        stt.transcribe(audio_file=input_file, transcription_output_file=output_path)
    
    if remove_local_file and os.path.isfile(local_audio_file):
        os.remove(local_audio_file)
        
    if wav_filename and os.path.isfile(wav_filename):
        os.remove(wav_filename)