from gtts import gTTS
from pathlib import Path
import argparse
from datetime import datetime, timezone
from speakcare_logging import SpeakcareLogger
from backend.speakcare_env import SpeakcareEnv


logger = SpeakcareLogger(__name__)

def text_to_speech(text: str, output_file: str):
    """
    Convert text to speech and save to a file.
    """
    tts = gTTS(text=text, lang='en')
    tts.save(output_file)
    logger.info(f"Speech saved to {output_file}")


def text_file_to_speech(input_file: str, output_file: str):
    """
    Convert text file to speech and save to a file.
    """
    with open(input_file, 'r') as file:
        text = file.read()
        text_to_speech(text, output_file)

if __name__ == "__main__":

    SpeakcareEnv.load_env()
    output_dir = SpeakcareEnv.get_audio_local_dir()
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

    output_filename = f'{output_dir}/{output_file_prefix}.{utc_string}.mp3'

    logger.info(f"Creating audio from {input_file} into {output_filename}")
    text_file_to_speech(input_file, output_filename)