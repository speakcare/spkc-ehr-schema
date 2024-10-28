from gtts import gTTS
from pathlib import Path
import argparse
from datetime import datetime, timezone
from speakcare_logging import create_logger
from os_utils import ensure_directory_exists

# Define your text
# text = """
#         Good afternoon Alice Johnson. I’m going to check your blood pressure now.
#         I’ll start by taking it while you're seated. I’ll use your left arm for this.
#         Please relax for a moment while I take the reading.
#         Your blood pressure is 130 over 85.
#         I’ll make a note of that. If there’s anything else, feel free to mention it later.
#         """

# # Initialize gTTS with your text and language (e.g., 'en' for English)
# tts = gTTS(text=text, lang='en')

# # Define the file path to save the audio
# speech_file_path = Path(__file__).parent / "blood_pressure.mp3"

# # Save the speech to a file
# tts.save(speech_file_path)

# print(f"Speech saved to {speech_file_path}")

logger = create_logger(__name__)

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

    output_dir = "out/recordings"
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

    ensure_directory_exists(output_dir) 
    logger.info(f"Creating audio from {input_file} into {output_filename}")
    text_file_to_speech(input_file, output_filename)