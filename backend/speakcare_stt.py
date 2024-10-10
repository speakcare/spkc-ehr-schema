import openai
#from openai import OpenAI
import argparse
from dotenv import load_dotenv
from datetime import datetime, timezone
import os
from os_utils import ensure_directory_exists
from speakcare_audio import record_audio
from speakcare_logging import create_logger

logger = create_logger(__name__)
load_dotenv()

# Set your OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")
#openai.api_key = 'your-api-key'

# New OpenAI API - not yet working
# client = OpenAI()

# transcript = client.audio.transcriptions.create(
#   model="whisper-1", 
#   file=audio_file
# )

def transcribe_audio(input_file="output.wav", output_file="output.txt"):

    transcript = None
    #client = OpenAI()

    try:
        with open(input_file, "rb") as audio_file:
     #       transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_file)

            transcript = openai.Audio.transcribe(model= "whisper-1", file=audio_file)

        # write the transcript to a text file
        with open(output_file, "w") as text_file:
            text_file.write(transcript['text'])
    except Exception as e:
        logger.error(f"Error transcribing audio: {e}")
        return 0

    transcription_length= len(transcript['text'])
    logger.info(f"Transcription saved to {output_file} length: {transcription_length} characters")
    return transcription_length
    


def record_and_transcribe():
    # Step 1: Record Audio
    output_filename = "output.wav"
    record_audio(duration=5, output_filename=output_filename)

    # Step 2: Transcribe Audio
    transcription = transcribe_audio(output_filename)
    print("Transcription:", transcription)

if __name__ == "__main__":

    output_dir = "out/transcriptions"
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

    output_filename = f'{output_dir}/{output_file_prefix}.{utc_string}.txt'

    ensure_directory_exists(output_filename) 
    logger.info(f"Transcribing audio from {input_file} into {output_filename}")
    transcribe_audio(input_file, output_filename)