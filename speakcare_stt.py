import openai
from speakcare_audio import record_audio

# Set your OpenAI API key
openai.api_key = 'your-api-key'

def transcribe_audio(filename="output.wav"):
    with open(filename, "rb") as audio_file:
        transcript = openai.Audio.transcribe("whisper-1", audio_file)
        return transcript["text"]



def record_and_transcribe():
    # Step 1: Record Audio
    output_filename = "output.wav"
    record_audio(duration=5, output_filename=output_filename)

    # Step 2: Transcribe Audio
    transcription = transcribe_audio(output_filename)
    print("Transcription:", transcription)

if __name__ == "__main__":
    record_and_transcribe()