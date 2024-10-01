from gtts import gTTS
from pathlib import Path
from pydub import AudioSegment

# Define your text
text = """
        Good afternoon Alice Johnson. I'm going to check your blood pressure now.
        I'll start by taking it while you're seated. I'll use your left arm for this.
        Please relax for a moment while I take the reading.
        Your blood pressure is 130 over 85.
        I'll make a note of that. If there's anything else, feel free to mention it later.
        """

# Initialize gTTS with your text and language (e.g., 'en' for English)
tts = gTTS(text=text, lang='en')

# Define the file path to save the audio
speech_file_path = Path(__file__).parent / "blood_pressure.mp3"

# Save the speech to a file
tts.save(speech_file_path)

# Load the audio file using pydub
audio = AudioSegment.from_mp3(speech_file_path)

# Increase the speed by reducing the duration (increase speed by 1.5x)
faster_audio = audio.speedup(playback_speed=1.5)

# Save the faster version
faster_speech_file_path = Path(__file__).parent / "blood_pressure_fast.mp3"
faster_audio.export(faster_speech_file_path, format="mp3")

print(f"Faster speech saved to {faster_speech_file_path}")




# from gtts import gTTS
# from pathlib import Path

# # Define your text
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
