import openai
from openai import OpenAI
import argparse
from dotenv import load_dotenv
from datetime import datetime, timezone
import os
from speakcare_audio import record_audio
from speakcare_logging import SpeakcareLogger
from boto3_session import Boto3Session
from speakcare_diarize import TranscribeAndDiarize
from speakcare_env import SpeakcareEnv
from os_utils import os_get_filename_without_ext

load_dotenv()
logger = SpeakcareLogger(__name__)
trnsAndDrz = TranscribeAndDiarize()

# Set your OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

def stt_whisper(input_file="output.wav", output_file="output.txt", append=False):

    transcript = None
    client = OpenAI()
    write_mode = "a" if append else "w"
    try:
        with open(input_file, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_file)

        # write the transcript to a text file
        logger.debug(f"Opening transcription output file {output_file} in {write_mode} mode")
        with open(output_file, write_mode) as text_file:
            text_file.write(transcript.text)
    except Exception as e:
        logger.log_exception("Error transcribing audio", e)
        return 0

    transcription_length= len(transcript.text)
    logger.info(f"Transcription saved to {output_file} length: {transcription_length} characters")
    return transcription_length

def stt_and_diarize_aws(boto3Session: Boto3Session, input_file="output.wav", output_file="output.txt", append=False):

    transcipt_file_key = None
    output_file_prefix = os_get_filename_without_ext(output_file)
    try:
        # with open(input_file, "rb") as audio_file:
        logger.info(f"Transcribing and diarizing audio from {input_file} into {output_file}. Output prefix: {output_file_prefix}")
        transcipt_file_key = trnsAndDrz.transcribe_and_recognize_speakers(input_file, output_file_prefix)
            # transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_file)

        if append:
            logger.info(f"Appending to {output_file}")
            boto3Session.s3_append_from_key(transcipt_file_key, output_file)
        else:
            logger.info(f"Copying to {output_file}")
            boto3Session.s3_copy_object(transcipt_file_key, output_file)
    except Exception as e:
        logger.log_exception("Error transcribing audio", e)
        return 0
    
    return boto3Session.s3_get_object_size(output_file)
    


    


def record_and_transcribe():
    # Step 1: Record Audio
    output_filename = "output.wav"
    record_audio(duration=5, output_filename=output_filename)

    # Step 2: Transcribe Audio
    transcription = stt_whisper(output_filename)
    print("Transcription:", transcription)

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Speakcare speech to text.')
    parser.add_argument('-o', '--output', type=str, default="output", help='Output file prefix (default: output)')
    parser.add_argument('-i', '--input', type=str, required=True, help='Input file name (default: input)')
    parser.add_argument('-m', '--model', type=str, 
                        choices=['whisper','aws'], default='whisper', help='Model: whisper or aws (default: whisper)')

    args = parser.parse_args()

    SpeakcareEnv.prepare_env()

    input_file = args.input
    output_file_prefix = args.output

    # Get the current UTC time
    utc_now = datetime.now(timezone.utc)

    # Format the datetime as a string without microseconds and timezone
    utc_string = utc_now.strftime('%Y-%m-%dT%H:%M:%S')

    output_filename = f'{SpeakcareEnv.get_texts_dir()}/{output_file_prefix}.{utc_string}.txt'

    if args.model == 'aws':
        boto3Session = Boto3Session()
        logger.info(f"AWS tanscribing and diarizing audio from {input_file} into {output_filename}")
        stt_and_diarize_aws(boto3Session, input_file, output_filename)
    else:
        logger.info(f"Whisper transcribing audio from {input_file} into {output_filename}")
        stt_whisper(input_file, output_filename)