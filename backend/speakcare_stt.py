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

load_dotenv()
logger = SpeakcareLogger(__name__)
trnsAndDrz = TranscribeAndDiarize()

# Set your OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

def transcribe_audio_whisper(input_file="output.wav", output_file="output.txt", append=False):

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

def transcribe_and_diarize_audio(boto3Session: Boto3Session, input_file="output.wav", output_file="output.txt", append=False):

    transcipt_file_key = None
    try:
        # with open(input_file, "rb") as audio_file:
        transcipt_file_key = trnsAndDrz.transcribe_and_recognize_speakers(input_file)
            # transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_file)

        if append:
            logger.debug(f"Appending to {output_file}")
            boto3Session.s3_append_from_key(transcipt_file_key, output_file)
        else:
            logger.debug(f"Copying to {output_file}")
            boto3Session.s3_copy_from_key(transcipt_file_key, output_file)
    except Exception as e:
        logger.log_exception("Error transcribing audio", e)
        return 0
    
    return boto3Session.s3_get_object_size(output_file)
    


    


def record_and_transcribe():
    # Step 1: Record Audio
    output_filename = "output.wav"
    record_audio(duration=5, output_filename=output_filename)

    # Step 2: Transcribe Audio
    transcription = transcribe_audio_whisper(output_filename)
    print("Transcription:", transcription)

if __name__ == "__main__":

    SpeakcareEnv.prepare_env()
    parser = argparse.ArgumentParser(description='Speakcare speech to text.')
    parser.add_argument('-o', '--output', type=str, default="output", help='Output file prefix (default: output)')
    parser.add_argument('-i', '--input', type=str, required=True, help='Input file name (default: input)')

    args = parser.parse_args()

    input_file = args.input
    output_file_prefix = args.output

    # Get the current UTC time
    utc_now = datetime.now(timezone.utc)

    # Format the datetime as a string without microseconds and timezone
    utc_string = utc_now.strftime('%Y-%m-%dT%H:%M:%S')

    output_filename = f'{SpeakcareEnv.texts_dir}/{output_file_prefix}.{utc_string}.txt'

    logger.info(f"Transcribing audio from {input_file} into {output_filename}")
    transcribe_audio_whisper(input_file, output_filename)