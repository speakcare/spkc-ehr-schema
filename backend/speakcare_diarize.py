import os
import json
import argparse
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


    def __do_diarization(self, audio_file: str, output_file_prefix: str='output', add_timestamps: bool = False):
        """Main method to transcribe audio and recognize speakers."""

        transcription_output_key, diarization_output_key, text_output_key = self.create_output_files_keys(output_file_prefix)

        self.transcriber.transcribe(audio_file, transcription_output_key)
        transcription_file = self.b3session.s3_get_object_uri(transcription_output_key)
        return self.recognize_transcript(audio_file = audio_file, 
                                transcription_file=transcription_file,
                                diarization_output_key=diarization_output_key,
                                text_output_key=text_output_key,
                                add_timestamps=add_timestamps)
        


    def diarize(self, audio_file:str, output_file:str="output.txt", append=False, add_timestamps: bool = False):

        transcipt_file_key = None
        output_file_prefix = os_get_filename_without_ext(output_file)
        try:
            self.logger.info(f"Transcribing and diarizing audio from {audio_file} into {output_file}. Output prefix: {output_file_prefix}")
            transcipt_file_key = self.__do_diarization(audio_file, output_file_prefix, add_timestamps)

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

    
    def recognize_transcript(self, audio_file: str, transcription_file: str, diarization_output_key: str, text_output_key: str, add_timestamps: bool = False):

        self.logger.info(f"recognize_speakers: transcription {transcription_file}. audio {audio_file}")
        diarized_transcription = self.recognizer.recognize(audio_file, transcription_file)
        
        self.logger.debug(f"Diarized transcription: {json.dumps(diarized_transcription, indent=4)}")
        
        # Write the diarized transcription to S3 into diariations folder
        self.b3session.s3_put_object(key=diarization_output_key, body=json.dumps(diarized_transcription))
        self.logger.info(f"Uploaded diarized transcription to 's3://{self.b3session.s3_get_bucket_name()}/{diarization_output_key}'")
        generated_transcript = self.recognizer.generate_recognized_text_transcript(add_timestamps=add_timestamps)
        self.b3session.s3_put_object(key=text_output_key, body=generated_transcript)
        self.logger.info(f"Uploaded text transcription to s3://{self.b3session.s3_get_bucket_name()}/{text_output_key}")

        return text_output_key

    

def main():
    SpeakcareEnv.load_env()
    logger = SpeakcareLogger(main.__name__)
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
    parser.add_argument('-b', '--batch', action='store_true', help="Batch mode: process all files in a directory or S3 bucket.")
    parser.add_argument('-d', '--add-timestamps', action='store_true', help="Add timestamps to the transcript.")
    args = parser.parse_args()

    
    audio_file = args.audio
    if not audio_file:
        print("Audio file is required.")
        exit(1)

    add_timestamps = args.add_timestamps

    b3session = Boto3Session.get_single_instance()
   
    if args.match_threshold:
        matching_similarity_threshold = args.match_threshold
    else:
        matching_similarity_threshold = float(os.getenv("MATCHING_SIMILARITY_THRESHOLD", 0.5))
    
    diarizer = SpeakcareDiarize(matching_similarity_threshold=matching_similarity_threshold)

    def is_s3_path(path):
        return path and b3session.s3_is_s3_uri(path)

    def list_audio_files(path):
        if is_s3_path(path):
            # List S3 objects with audio extensions
            bucket, prefix = b3session.s3_uri_split_bucket_key(path)
            all_files = b3session.s3_list_folder(folder_prefix=prefix, bucket=bucket)
            return [f"s3://{bucket}/{key}" for key in all_files if key.lower().endswith(('.wav', '.mp3', '.m4a', '.flac', '.ogg'))]
        else:
            return [os.path.join(path, f) for f in os.listdir(path) if f.lower().endswith(('.wav', '.mp3', '.m4a', '.flac', '.ogg'))]

    def list_transcript_files(path):
        if not path:
            return None
        if is_s3_path(path):
            bucket, prefix = b3session.s3_uri_split_bucket_key(path)
            all_files = b3session.s3_list_folder(folder_prefix=prefix, bucket=bucket)
            return [f"s3://{bucket}/{key}" for key in all_files if key.lower().endswith('.json')]
        else:
            return [os.path.join(path, f) for f in os.listdir(path) if f.lower().endswith('.json')]

    def match_transcript(audio_file, transcript_files):
        if not transcript_files:
            return None
        audio_base = os.path.splitext(os.path.basename(audio_file))[0]
        for t in transcript_files:
            t_base = os.path.splitext(os.path.basename(t))[0]
            if t_base.startswith(audio_base):
                logger.info(f"Audio file {audio_file} matches transcript file {t}")
                return t
        return None

    def process_file(audio_file, input_file_path, function, diarizer: SpeakcareDiarize):
        logger.info(f"Function {function} processing audio file {audio_file}, input file {input_file_path}")
        remove_audio_local_file = False
        converted_wav_file = None
        local_audio_file, remove_audio_local_file = b3session.s3_localize_file(audio_file)
        audio_prefix = os_concat_current_time(os_get_filename_without_ext(audio_file))
        if not audio_is_wav(local_audio_file):
            converted_wav_file = audio_convert_to_wav(local_audio_file)
            local_audio_file = converted_wav_file
        try:
            match function:
                case "full":
                    diarized_output_file = f'{audio_prefix}-diarized.txt'
                    diarizer.diarize(audio_file=local_audio_file, output_file=diarized_output_file, add_timestamps=add_timestamps)
                case "transcribe":
                    transcription, _, _ = diarizer.create_output_files_keys(audio_prefix)
                    diarizer.transcriber.transcribe(local_audio_file, transcription)
                case "recognize":
                    _, diarization, text = diarizer.create_output_files_keys(audio_prefix)
                    diarizer.recognize_transcript(audio_file=local_audio_file, 
                                                transcription_file = input_file_path,
                                                diarization_output_key=diarization,
                                                text_output_key=text,
                                                add_timestamps=add_timestamps)
                case _:
                    print(f"Invalid function '{function}'")
                    return
        except Exception as e:
            print(f"Error occurred processing {audio_file}: {e}")
        finally:
            if remove_audio_local_file and local_audio_file and os.path.isfile(local_audio_file):
                os.remove(local_audio_file)
            elif converted_wav_file and os.path.isfile(converted_wav_file):
                os.remove(converted_wav_file)


    if args.batch:
        audio_files = list_audio_files(args.audio)
        logger.info(f"Found {len(audio_files)} audio files in {args.audio}")
        transcript_files = list_transcript_files(args.input) if args.input else None
        for i, audio_file in enumerate(audio_files):
            logger.info(f"Processing audio file {i+1} of {len(audio_files)}: {audio_file}")
            input_file_path = match_transcript(audio_file, transcript_files) if transcript_files else None
            process_file(audio_file, input_file_path, args.function, diarizer)
        return

    else:
        process_file(audio_file, args.input, args.function, diarizer)
        return


if __name__ == "__main__":
    main()