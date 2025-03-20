import os
import json
import argparse
from dotenv import load_dotenv
import warnings
from boto3_session import Boto3Session
from speakcare_logging import SpeakcareLogger
from speakcare_env import SpeakcareEnv
from os_utils import os_get_filename_without_ext, os_concat_current_time
from speakcare_stt import SpeakcareAWSTranscribe
from speakcare_audio import audio_is_wav, audio_convert_to_wav
from speakcare_recognizer import TranscriptRecognizer
from speakcare_embeddings import SpeakcareEmbeddings
from speakcare_vocoder import VocoderFactory

warnings.filterwarnings("ignore", category=FutureWarning)

# Load environment variables and configure logging
if not load_dotenv("./.env"):
    print("No .env file found")
    exit(1)

SpeakcareEnv.load_env()



class SpeakcareDiarize:
    def __init__(self, matching_similarity_threshold: float = 0.75):
        self.logger = SpeakcareLogger(SpeakcareDiarize.__name__)
        self.b3session =  Boto3Session.get_single_instance()
        self.speakers_table_name = self.b3session.dynamo_get_table_name("speakers")
        self.transcriber = SpeakcareAWSTranscribe()
        self.recognizer = None
        self.matching_similarity_threshold: float =float(matching_similarity_threshold)
        self.__init_speaker_recognition()


    def __init_speaker_recognition(self):

        self.logger.info(f"Matching similarity threshold: {self.matching_similarity_threshold}")
        vocoder = VocoderFactory.create_vocoder()
        embedding_store = SpeakcareEmbeddings(vocoder=vocoder, matching_similarity_threshold=self.matching_similarity_threshold)
        self.recognizer = TranscriptRecognizer(vocoder=vocoder, embedding_store=embedding_store, work_dir=SpeakcareEnv.get_audio_local_dir())


    @staticmethod
    def create_output_files_keys(output_file_prefix:str):
        """Create output file keys for transcription, diarization, and text."""                
        transcription_output_key = f"{SpeakcareEnv.get_transcriptions_dir()}/{output_file_prefix}-transcription.json"
        diarization_output_key = f"{SpeakcareEnv.get_diarizations_dir()}/{output_file_prefix}-diarization.json"
        text_output_key = f"{SpeakcareEnv.get_texts_dir()}/{output_file_prefix}-text.txt"
        
        return transcription_output_key, diarization_output_key, text_output_key


    def __do_diarization(self, audio_file: str, output_file_prefix: str='output'):
        """Main method to transcribe audio and recognize speakers."""

        transcription_output_key, diarization_output_key, text_output_key = self.create_output_files_keys(output_file_prefix)

        self.transcriber.transcribe(audio_file, transcription_output_key)
        transcription_file = self.b3session.s3_get_object_uri(transcription_output_key)
        return self.recognize_transcript(audio_file = audio_file, 
                                transcription_file=transcription_file,
                                diarization_output_key=diarization_output_key,
                                text_output_key=text_output_key)
        


    def diarize(self, audio_file:str, output_file:str="output.txt", append=False):

        transcipt_file_key = None
        output_file_prefix = os_get_filename_without_ext(output_file)
        try:
            self.logger.info(f"Transcribing and diarizing audio from {audio_file} into {output_file}. Output prefix: {output_file_prefix}")
            transcipt_file_key = self.__do_diarization(audio_file, output_file_prefix)

            if append:
                self.logger.info(f"Appending to {output_file}")
                self.b3session.s3_append_from_key(transcipt_file_key, output_file)
            else:
                self.logger.info(f"Copying to {output_file}")
                self.b3session.s3_copy_object(transcipt_file_key, output_file)
        except Exception as e:
            self.logger.log_exception("Error transcribing audio", e)
            return 0
        
        return self.b3session.s3_get_object_size(output_file)

    
    def recognize_transcript(self, audio_file: str, transcription_file: str, diarization_output_key: str, text_output_key: str):

        self.logger.info(f"recognize_speakers: transcription {transcription_file}. audio {audio_file}")
        diarized_transcription = self.recognizer.recognize(audio_file, transcription_file)
        
        self.logger.debug(f"Diarized transcription: {json.dumps(diarized_transcription, indent=4)}")
        
        # Write the diarized transcription to S3 into diariations folder
        self.b3session.s3_put_object(key=diarization_output_key, body=json.dumps(diarized_transcription))
        self.logger.info(f"Uploaded diarized transcription to 's3://{self.b3session.s3_get_bucket_name()}/{diarization_output_key}'")
        generated_transcript = self.recognizer.generate_recognized_text_transcript()
        self.b3session.s3_put_object(key=text_output_key, body=generated_transcript)
        self.logger.info(f"Uploaded text transcription to s3://{self.b3session.s3_get_bucket_name()}/{text_output_key}")

        return text_output_key

    

def main():
    parser = argparse.ArgumentParser(description="Speaker Recognition Tool")
    choices = ["full", "transcribe", "recognize"]
    parser.add_argument(
        '-f', '--function',
        type=str, 
        choices=choices, 
        required=True, 
        help=f"Function: {choices}"
    )
    parser.add_argument('-a', '--audio', type=str, required=True, help="Local path to audio file.")
    parser.add_argument('-i', '--input', type=str, help="S3 path to the specific input file.")
    parser.add_argument('-t', '--match-threshold', type=float, help="Matching similarity threshold.")
    args = parser.parse_args()

    b3session = Boto3Session.get_single_instance()
    matching_similarity_threshold = float(os.getenv("MATCHING_SIMILARITY_THRESHOLD", 0.5))

    audio_file = args.audio
    if not audio_file:
        print("Audio file is required.")
        exit(1)

    input_file_path = args.input
    audio_prefix = os_concat_current_time(os_get_filename_without_ext(audio_file)) if audio_file else None

    remove_audio_local_file = False
    audio_file, remove_audio_local_file = b3session.s3_localize_file(audio_file)
    converted_wav_file = None
    matching_similarity_threshold = float(os.getenv("MATCHING_SIMILARITY_THRESHOLD", 0.5))
    
    if args.match_threshold:
        matching_similarity_threshold = args.match_threshold
    
    diarizer = SpeakcareDiarize(matching_similarity_threshold=matching_similarity_threshold)

    if not audio_is_wav(audio_file):
        converted_wav_file = audio_convert_to_wav(audio_file)
        audio_file = converted_wav_file
    try:
        match args.function:
            case "full":
                diarized_output_file = f'{audio_prefix}-diarized.txt'
                diarizer.diarize(audio_file=audio_file, output_file=diarized_output_file)

            case "transcribe":
                transcription, _, _ = diarizer.create_output_files_keys(audio_prefix)
                diarizer.transcriber.transcribe(audio_file, transcription)

            case "recognize":
                # The input file is a post recognition file
                _, diarization, text = diarizer.create_output_files_keys(audio_prefix)
                diarizer.recognize_transcript(audio_file=audio_file, 
                                            transcription_file = input_file_path,
                                            diarization_output_key=diarization,
                                            text_output_key=text)
            case _:
                print(f"Invalid function '{args.function}'")
                exit(1)
    except Exception as e:
        print(f"Error occurred: {e}")
    finally:
        if remove_audio_local_file and audio_file and os.path.isfile(audio_file):
            os.remove(audio_file)
        elif converted_wav_file and os.path.isfile(converted_wav_file):
            os.remove(converted_wav_file)

if __name__ == "__main__":
    main()