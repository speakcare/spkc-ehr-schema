import openai
import os
openai.api_key = os.getenv("OPENAI_API_KEY")
audio_path = 'Weighing_a_patient.mp3'

def transcribe_audio(audio_path):
    with open(audio_path, "rb") as audio_file:
        transcript = openai.Audio.transcribe(
            model="whisper-1", 
            file=audio_file
        )
    return transcript['text']

if __name__ == "__main__":

    transcription = transcribe_audio(audio_path)
    print(transcription)
    