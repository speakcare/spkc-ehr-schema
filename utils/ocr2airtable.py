import openai
import os
from dotenv import load_dotenv
from pyannote.audio import Pipeline
import wave

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
huggingface_token = os.getenv("HUGGINGFACE_TOKEN")

client = openai.OpenAI(api_key=openai.api_key)

# Diarization pipeline
pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization", use_auth_token=huggingface_token)

def diarize_audio(audio_path):
    return pipeline(audio_path)

def transcribe_audio(file_path, language="he"):
    with open(file_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language=language,
            response_format="verbose_json"
        )
    return transcript

def combine_speakers_with_transcript(diarization_result, whisper_result):
    # Extract transcript segments with time
    segments = whisper_result.segments
    speaker_segments = []

    for seg in segments:
        start = seg['start']
        end = seg['end']
        text = seg['text']

        # Match this to the diarization result
        speaker_label = "Unknown"
        for turn in diarization_result.itertracks(yield_label=True):
            s, e, speaker = turn
            if s <= start <= e or s <= end <= e:
                speaker_label = speaker
                break

        speaker_segments.append(f"{speaker_label}: {text.strip()}")

    return "\n".join(speaker_segments)

if __name__ == "__main__":
    wav_file = "/Users/gilgeva/Downloads/Goat.wav"

    print("Transcribing...")
    transcript = transcribe_audio(wav_file)

    print("Running diarization...")
    diarization = diarize_audio(wav_file)

    print("Combining speaker labels...")
    labeled_transcript = combine_speakers_with_transcript(diarization, transcript)

    output_path = "transcription_with_speakers.txt"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(labeled_transcript)

    print(f"\n✅ Saved to: {output_path}")
