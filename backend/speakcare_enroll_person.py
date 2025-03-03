import os
import argparse
import random
import json
from datetime import datetime, timezone
from speakcare_diarize import SpeakerType, TranscribeAndDiarize
from speakcare_emr_utils import EmrUtils
from boto3_session import Boto3Session
from speakcare_env import SpeakcareEnv
from speakcare_audio import audio_convert_to_wav
from speakcare_logging import SpeakcareLogger
from os_utils import os_ensure_file_directory_exists, os_get_file_extension
from speakcare_stt import transcribe_audio_whisper
from speakcare_llm import openai_complete_schema_from_transcription


class SpeakcareEnrollPerson():
    def __init__(self):
        self.logger = SpeakcareLogger(SpeakcareEnrollPerson.__name__)
        self.b3session = Boto3Session(SpeakcareEnv.get_working_dirs())

    
    def __transcribe_audio(self, audio_filename:str, output_file_prefix:str="output"):
                # Step 1: Verify the audio file exists
        # check if in s3 or local
        file_exist = False
        is_s3_file = False
        if audio_filename.startswith("s3://"):
            file_exist = self.b3session.s3_uri_check_object_exists(audio_filename)
            is_s3_file = True
        else:
            file_exist = os.path.isfile(audio_filename)
            is_s3_file = False
        
        if not file_exist:
            err = f"Audio file not found or not file type: {audio_filename}"
            self.logger.error(err)
            raise Exception(err)

        self.logger.debug(f"Preparing s3 audio location. Output prefix: {output_file_prefix}, Audio file: {audio_filename}, File extension: {os_get_file_extension(audio_filename)}")  
        dest_s3_persons_location = f'{SpeakcareEnv.get_persons_dir()}/{output_file_prefix}{os_get_file_extension(audio_filename)}'

        if is_s3_file:
            # download the file
            audio_local_file = f'{SpeakcareEnv.get_persons_local_dir()}/{os.path.basename(audio_filename)}'
            os_ensure_file_directory_exists(audio_local_file)
            self.b3session.s3_uri_download_file(audio_filename, audio_local_file)
            if audio_filename != dest_s3_persons_location:
                # upload the file to s3 destination folder
                self.b3session.s3_upload_file(audio_local_file, dest_s3_persons_location)
        else:
            # put the file in s3 destination folder
            self.b3session.s3_upload_file(audio_filename, dest_s3_persons_location)
            audio_local_file = audio_filename

        # Step 2: Transcribe Audio (speech to text)
        transciption_output_file = f'{SpeakcareEnv.get_persons_local_dir()}/{output_file_prefix}-transcribe.txt'
        os_ensure_file_directory_exists(transciption_output_file)
        
        if os.path.isfile(transciption_output_file):
            os.remove(transciption_output_file) #TODO: temp solution for left over files.

        self.__do_transcription(audio_local_file, transciption_output_file)
        # uploade the trascript file to s3
        dest_s3_transcription_location = f'{SpeakcareEnv.get_persons_dir()}/{os.path.basename(transciption_output_file)}'
        self.b3session.s3_upload_file(transciption_output_file, dest_s3_transcription_location)
        return transciption_output_file, is_s3_file, audio_local_file

    def __do_transcription(self, audio_filename:str, transcribe_ouptut_file:str):
        # if audio file is not wav, convert to wav
        wav_filename=""
        if not audio_filename.endswith(".wav"):
            file_ext = os_get_file_extension(audio_filename)
            wav_filename = audio_filename.replace(file_ext, ".wav")
            self.logger.info(f"Converting {file_ext} to .wav: {audio_filename} -> {wav_filename}")
            audio_convert_to_wav(audio_filename, wav_filename)
            audio_filename = wav_filename
        
        len = transcribe_audio_whisper(audio_filename, transcribe_ouptut_file)
        if len:
            self.logger.info(f"Transcription saved to {transcribe_ouptut_file} length: {len} characters")
        else:
            self.logger.error(f"Error transcribing audio file {audio_filename}")

        if wav_filename:
            # remove the wav file
            os.remove(wav_filename)

    def __upload_person_record_to_s3(self, person_role: SpeakerType, person_data:dict, output_file_prefix:str="output"):
        person_data_file = f'{SpeakcareEnv.get_persons_dir()}/{output_file_prefix}-{person_role.value.lower()}.json'
        person_data_local_file = f'{SpeakcareEnv.get_persons_local_dir()}/{os.path.basename(person_data_file)}'
        with open(person_data_local_file, 'w') as f:
            f.write(json.dumps(person_data, indent=4))

        self.b3session.s3_upload_file(person_data_local_file, person_data_file)
        return person_data_file
    
        
    def __generate_patient_record(self, transcription_filename:str, output_file_prefix:str="output"):
        
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

        patient_data= openai_complete_schema_from_transcription(system_prompt, prompt, transcription, json_schema)
        
        self.logger.debug(f"Patient data: {patient_data}")
        return patient_data

    
    def __generate_nurse_record(self, transcription_filename:str, output_file_prefix:str="output"):
        
        prompt = f'''
            You are given a transcription of a recording of a nurse employed by healthcare institution. 
            The transcriptions contains the onboarding conversation in which the nurse is presenting herself.
            Your task is to fill the nurse's information based on the transcription in the provided json_schema.
            Based on the transcription, respond with a valid json object formatted according to the provided json_schema, and nothing else.
            Please fill in the json properties if and only if you are sure of the answers.
            Do not assume any values, only fill in the properties that can explicitly be dervied from he transcription.
            In any case you cannot explicitly derive an answer from the transcription, you must set the value to null. 
            If you are not sure or a field is not mentioned in the transcription, set the value to null.
            If you are sure that a field is not applicable, set the value to null.
        '''

        system_prompt="You are an expert in parsing onboarding transcription and filling nurses employment forms."

        json_schema = EmrUtils.get_nurses_table_schema()
        transcription = ""
        with open(transcription_filename) as f:
            transcription = f.read()

        nurse_data= openai_complete_schema_from_transcription(system_prompt, prompt, transcription, json_schema)
        
        self.logger.debug(f"Nurse data: {nurse_data}")
        return nurse_data

    def __generate_person_record(self, transcription_filename:str, output_file_prefix:str="output"):
        # generate either patient or nurse record

        prompt = f'''
            You are given a transcription of a introduction of a person, either a patient admitted to, or a nurse employed by, a healthcare institution. 
            The transcriptions contains the onboarding conversation in which the person is presenting themselves.
            Your task is to fill the person's information record based on the transcription in to the provided json_schema.

            Based on the transcription, first decide if this is a patient or a nurse, it must be either and never both.
            Next, generate a JSON response following the provided schema. 
            The schema has a "fileds" property that contains the fields for both patients and nurses, named patients_fields and nurses_fields respectively.
            If table_name is 'Patients', populate patients_fields and set nurses_fields to null. 
            If table_name is 'Nurses', populate nurses_fields and set patients_fields to null. Always follow this rule."
            Please fill in the json properties if and only if you are sure of the answers.
            Do not assume any values, only fill in the properties that can explicitly be dervied from he transcription.
            In any case you cannot explicitly derive an answer from the transcription, you must set the value to null. 
            If you are sure that a field is not applicable, set the value to null.
        '''

        system_prompt="You are an expert in parsing onboarding transcription and filling nurses employment forms."
        json_schema = {
            "title": "Person Record",
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "enum": ["Patients", "Nurses"],
                    "description": "Determines whether the entry is for a Patient or a Nurse"
                },
                "fields": {
                    "type": "object",
                    "description": "The specific fields for the selected table",
                    "properties": {
                        "patients_fields": EmrUtils.get_patients_table_fields(),
                        "nurses_fields": EmrUtils.get_nurses_table_fields(),
                    },
                    "required": ["patients_fields", "nurses_fields"],
                    "additionalProperties": False
                }
            },
            "required": ["table_name", "fields"],
            "additionalProperties": False
        }
        transcription = ""
        with open(transcription_filename) as f:
            transcription = f.read()

        person_data= openai_complete_schema_from_transcription(system_prompt, prompt, transcription, json_schema)
        
        self.logger.debug(f"Person data: {person_data}")
        return person_data

    def __add_patient(self, patient_fields:dict, audio_local_file:str):
        # Step 3: Create patient person record
        patient_name = patient_fields.get('FullName', None)
        if patient_name:
            emr_patient_record, message = EmrUtils.add_patient(patient_fields)
            if not emr_patient_record:
                self.logger.error(f"Error adding patient record: {message}")
            # Step 4: Create the speech embeddings for this person and save to dynamodb
            transcriber = TranscribeAndDiarize()
            transcriber.add_voice_sample(file_path = audio_local_file, speaker_type= SpeakerType.PATIENT, speaker_name=patient_name)
        else:
            self.logger.error("Patient name not found in transcription. Cannot create EMR record.")
        return patient_name


    def __add_nurse(self, nurse_fields:dict, audio_local_file:str):
        # Step 3: Create nurse record
        nurse_name = nurse_fields.get('Name', None)
        if nurse_name:
            emr_nurse_record, message = EmrUtils.add_nurse(nurse_fields)
            if not emr_nurse_record:
                self.logger.error(f"Error adding nurse record: {message}")
            # Step 4: Create the speech embeddings for this person and save to dynamodb
            transcriber = TranscribeAndDiarize()
            transcriber.add_voice_sample(file_path = audio_local_file, speaker_type= SpeakerType.NURSE, speaker_name=nurse_name)
        else:
            self.logger.error("Nurse name not found in transcription. Cannot create EMR record.")
        return nurse_name



    # Public methods

    # Enroll a patient
    def enroll_patient(self, audio_filename:str, output_file_prefix:str="output", dryrun: bool=False):

        transciption_output_file, is_s3_file, audio_local_file = self.__transcribe_audio(audio_filename, output_file_prefix)
        # Step 3: Prepare patient data
        patient_data = self.__generate_patient_record(transciption_output_file)
        # store person data in s3
        self.__upload_person_record_to_s3(SpeakerType.PATIENT, patient_data, output_file_prefix)
        
        if not dryrun:
            patient_fields = patient_data.get('fields', {})
            self.__add_patient(patient_fields, audio_local_file)
        
        else:
            self.logger.info("Dryrun mode. EMR record will not be created.")
        #end enroll_patient cleanup
        if is_s3_file and os.path.isfile(audio_local_file):
            # remove the local audio file
            os.remove(audio_local_file)

    # Enroll a nurse
    def enroll_nurse(self, audio_filename:str, output_file_prefix:str="output", dryrun: bool=False):

        transciption_output_file, is_s3_file, audio_local_file = self.__transcribe_audio(audio_filename, output_file_prefix)
        # Step 3: Prepare patient data
        nurse_data = self.__generate_nurse_record(transciption_output_file)
        # store person data in s3
        self.__upload_person_record_to_s3(SpeakerType.NURSE, nurse_data, output_file_prefix)
        
        if not dryrun:
            nurse_fields = nurse_data.get('fields', {})
            self.__add_nurse(nurse_fields, audio_local_file)
        
        else:
            self.logger.info("Dryrun mode. EMR record will not be created.")
        #end enroll_patient cleanup
        if is_s3_file and os.path.isfile(audio_local_file):
            # remove the local audio file
            os.remove(audio_local_file)

    
    # Enroll a person, detect if nurse or patient from the transcription
    def enroll_person(self, audio_filename:str, output_file_prefix:str="output", dryrun: bool=False):

        transciption_output_file, is_s3_file, audio_local_file = self.__transcribe_audio(audio_filename, output_file_prefix)
        # Step 3: Prepare patient data
        person_data = self.__generate_person_record(transciption_output_file)

        table_name = person_data.get('table_name', None)
        self.logger.info(f"Enrolling person of type {table_name}")
        if not table_name:
            self.logger.error("Table name not found in transcription. Cannot create EMR record.")
            return None
        
        if table_name == "Patients":
            role = SpeakerType.PATIENT
        elif table_name == "Nurses":
            role = SpeakerType.NURSE
        else:
            self.logger.error("Inavalid table name {table_name}. Cannot create EMR record.")
            return None
        
        # store person data in s3
        self.__upload_person_record_to_s3(SpeakerType.NURSE, person_data, output_file_prefix)
        person_name = None
        person_role = role.value.lower()
        if not dryrun:
            if role == SpeakerType.PATIENT:
                self.logger.info("enroll_person: Adding patient")
                patient_fields = person_data.get('fields', {}).get('patients_fields', {})
                person_name = self.__add_patient(patient_fields, audio_local_file)
            else:
                self.logger.info("enroll_person: Adding nurse")
                nurse_fields = person_data.get('fields', {}).get('nurses_fields', {})
                person_name = self.__add_nurse(nurse_fields, audio_local_file)
        
        else:
            self.logger.info("Dryrun mode. EMR record will not be created.")
        #end enroll_patient cleanup
        if is_s3_file and os.path.isfile(audio_local_file):
            # remove the local audio file
            os.remove(audio_local_file)

        return {"person": person_name, "role": person_role}



def main():
    # for testing from command line
    logger = SpeakcareLogger(__name__)
    SpeakcareEnv.prepare_env()

    parser = argparse.ArgumentParser(description='Speakcare person enrollment.')
    # Add arguments
    parser.add_argument('-d', '--dryrun', action='store_true',
                        help='If dryrun, write JSON only and do not enroll person')
    parser.add_argument('-i', '--input-recording', type=str, required=True, 
                        help='Name of input recording file for enrollment. Local file or s3 file s3://{bucket-name}/{file-name}.')
    parser.add_argument('-o', '--output-prefix', type=str, default="output",
                        help='Output file prefix (default: output)')
    parser.add_argument('-t', '--type', type=str, default="any",
                        help="Type of person to enroll ('patient', 'nurse', 'any')")

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
    speaker_type = args.type
    # enroll the patient
    enroller = SpeakcareEnrollPerson()
    if speaker_type == "patient":
        enroller.enroll_patient(audio_filename, output_file_prefix, dryrun)
    elif speaker_type == "nurse":
        enroller.enroll_nurse(audio_filename, output_file_prefix, dryrun)
    else:
        enroller.enroll_person(audio_filename, output_file_prefix, dryrun)

if __name__ == "__main__":
    main()
    print("Speakcare enrollment completed  ...")
