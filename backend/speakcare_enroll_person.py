import os
import argparse
import random
import json
from datetime import datetime, timezone
from speakcare_diarize import SpeakerType, TranscribeAndDiarize
from speakcare_emr_utils import EmrUtils
from boto3_session import Boto3Session
from speakcare_env import SpeakcareEnv
from speakcare_audio import convert_mp4_to_wav
from speakcare_logging import SpeakcareLogger
from os_utils import ensure_file_directory_exists
from speakcare_stt import transcribe_audio_whisper
from speakcare_llm import openai_complete_schema_from_transcription

def get_file_extension(filename):
    """Get the file extension from a given filename or path."""
    _, ext = os.path.splitext(filename)
    return ext

class SpeakcareEnrollPerson():
    def __init__(self):
        self.logger = SpeakcareLogger(SpeakcareEnrollPerson.__name__)
        self.b3session = Boto3Session(SpeakcareEnv.get_working_dirs())
        
    def enroll_patient(self, audio_filename:str, output_file_prefix:str="output", dryrun: bool=False):

        # Step 1: Verify the audio file exists
        # check if in s3 or local
        file_exist = False
        is_s3_file = False
        if audio_filename.startswith("s3://"):
            file_exist = self.b3session.s3_check_file_exists(audio_filename)
            is_s3_file = True
        else:
            file_exist = os.path.isfile(audio_filename)
            is_s3_file = False
        
        if not file_exist:
            err = f"Audio file not found or not file type: {audio_filename}"
            self.logger.error(err)
            raise Exception(err)

        dest_s3_persons_location = f'{SpeakcareEnv.get_persons_dir()}/{output_file_prefix}.{get_file_extension(audio_filename)}'

        if is_s3_file:
            # put the file in s3 destination folder
            self.logger.debug(f"Copying {audio_filename} to {dest_s3_persons_location}")
            self.b3session.s3_copy_object(audio_filename, dest_s3_persons_location)
            # download the file
            audio_local_file = f'{SpeakcareEnv.get_persons_local_dir()}/{os.path.basename(audio_filename)}'
            ensure_file_directory_exists(audio_local_file)
            self.b3session.s3_download_file(audio_filename, audio_local_file)
        else:
            # put the file in s3 destination folder
            self.b3session.s3_upload_file(audio_filename, dest_s3_persons_location)
            audio_local_file = audio_filename

        # Step 2: Transcribe Audio (speech to text)
        transciption_output_file = f'{SpeakcareEnv.get_persons_local_dir()}/{output_file_prefix}-transcribe.txt'
        ensure_file_directory_exists(transciption_output_file)
        self.transcribe_audio(audio_local_file, transciption_output_file)
        # uploade the trascript file to s3
        dest_s3_transcription_location = f'{SpeakcareEnv.get_persons_dir()}/{os.path.basename(transciption_output_file)}'
        self.b3session.s3_upload_file(transciption_output_file, dest_s3_transcription_location)

        patient_data = self.prepare_patient_data(transciption_output_file)
        self.logger.debug(f"Patient data: {patient_data}")
        patient_data_file = f'{SpeakcareEnv.get_persons_dir()}/{output_file_prefix}-patient.json'
        patient_data_local_file = f'{SpeakcareEnv.get_persons_local_dir()}/{os.path.basename(patient_data_file)}'
        with open(patient_data_local_file, 'w') as f:
            f.write(json.dumps(patient_data, indent=4))

        self.b3session.s3_upload_file(patient_data_local_file, patient_data_file)

        if dryrun:
            self.logger.info("Dryrun mode. EMR record will not be created.")
            return
        
        else:
            # Step 3: Create EMR person record
            patient_fields = patient_data.get('fields', {})
            patient_name = patient_fields.get('FullName', None)
            if patient_name:
                emr_patient_record, message = EmrUtils.add_patient(patient_data.get('fields', {}))
                if not emr_patient_record:
                    self.logger.error(f"Error adding patient record: {message}")
                # Step 4: Create the speech embeddings for this person and save to dynamodb
                transcriber = TranscribeAndDiarize()
                transcriber.add_voice_sample(file_path = audio_local_file, speaker_type= SpeakerType.PATIENT, speaker_name=patient_name)
            else:
                self.logger.error("Patient name not found in transcription. Cannot create EMR record.")
            #         
        #end enroll_patient cleanup
        if is_s3_file:
            # remove the local audio file
            os.remove(audio_local_file)

    def transcribe_audio(self, audio_filename:str, transcribe_ouptut_file:str):
        # if audio file is mp4, convert to wav
        is_mp4 = False
        wav_filename=""
        if audio_filename.endswith(".mp4"):
            is_mp4 = True
            wav_filename = audio_filename.replace(".mp4", ".wav")
            self.logger.info(f"Converting mp4 to wav: {audio_filename} -> {wav_filename}")
            convert_mp4_to_wav(audio_filename, wav_filename)
            audio_filename = wav_filename
        
        len = transcribe_audio_whisper(audio_filename, transcribe_ouptut_file)
        if len:
            self.logger.info(f"Transcription saved to {transcribe_ouptut_file} length: {len} characters")
        else:
            self.logger.error(f"Error transcribing audio file {audio_filename}")

        if wav_filename:
            # remove the wav file
            os.remove(wav_filename)

    
    def prepare_patient_data(self, transcription_filename:str):
        
        prompt = f'''
            You are given a transcription of a recording of a patient admitted to healthcare institution. 
            The transcriptions contains the conversation between the patient and the healthcare provider in which the patient is presenting themselves.
            Your task is to fill the patient's information based on the transcription in the provided json_schema.
            Based on the transcription, respond with a valid json object formatted according to the provided json_schema, and nothing else.
            Please fill in the json properties if and only if you are sure of the answers.
            Do not assume any values, only fill in the properties that can explicitly be dervied from he transcription.
            In any case you cannot explicitly derive an answer from the transcription, you must set the value to null. 
            If you are not sure or a field is not mentioned in the transcription, set the value to null.
            If you are sure that a field is not applicable, set the value to null.
        '''

        system_prompt="You are an expert in parsing medical transcription and filling admission forms."

        json_schema = EmrUtils.get_patients_table_schema()
        transcription = ""
        with open(transcription_filename) as f:
            transcription = f.read()

        return openai_complete_schema_from_transcription(system_prompt, prompt, transcription, json_schema)
        


    def add_nurse(audio_filename:str):
        pass




def main():
    # for testing from command line
    logger = SpeakcareLogger(__name__)
    SpeakcareEnv.prepare_env()

    parser = argparse.ArgumentParser(description='Speakcare person enrollment.')
    # Add arguments
    parser.add_argument('-d', '--dryrun', action='store_true',
                        help='If dryrun, write JSON only and do not enroll person')
    parser.add_argument('-i', '--input-recording', type=str, required=True, 
                        help='Name of input recording file for enrollment.')
    parser.add_argument('-o', '--output-prefix', type=str, default="output",
                        help='Output file prefix (default: output)')

    # Parse arguments
    args = parser.parse_args()

    output_file_prefix = "output"
    if args.output_prefix:
        output_file_prefix = args.output_prefix

    dryrun = args.dryrun
    if dryrun:
        logger.info("Dryrun mode enabled. EMR record will not be created.")

    rnd = random.randint(1000, 9999)
    utc_now = datetime.now(timezone.utc)
    # Format the datetime as a string without microseconds and timezone
    utc_string = utc_now.strftime('%Y-%m-%dT%H:%M:%S')
    output_file_prefix = f'{output_file_prefix}.{utc_string}_{rnd}'

    audio_filename = args.input_recording
    # enroll the patient
    enroller = SpeakcareEnrollPerson()
    enroller.enroll_patient(audio_filename, output_file_prefix, dryrun)

if __name__ == "__main__":
    main()
    print("Speakcare enrollment completed  ...")
