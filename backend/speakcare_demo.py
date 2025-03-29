#!/usr/bin/env python3

from typing import List
import os
from speakcare_logging import SpeakcareLogger
from speakcare_stt import SpeakcareOpenAIWhisper
from speakcare_charting import create_chart_completion
from speakcare_emr_utils import EmrUtils
from boto3_session import Boto3Session
from speakcare_env import SpeakcareEnv
from os_utils import os_get_filename_without_ext, os_concat_current_time
from speakcare_audio import audio_record


SpeakcareEnv.load_env()
DB_DIRECTORY = os.getenv("DB_DIRECTORY", "db")
logger = SpeakcareLogger(__name__)
boto3Session = Boto3Session.get_single_instance()

supported_tables = EmrUtils.get_table_names()
transciber = SpeakcareOpenAIWhisper()

def speakcare_demo_process_audio(audio_files: List[str], tables: List[str], output_file_prefix:str=None, update_emr: bool=True):
    """
    Transcribe audio, convert transcription to EMR record
    """    
    # prepare file names
    # use output_file_prefix if provided, otherwise use the basename of the first audio file
    _output_prefix = output_file_prefix if output_file_prefix\
                          else os_concat_current_time(os_get_filename_without_ext(audio_files[0]))

    transcript_filename = f'{SpeakcareEnv.get_texts_local_dir()}/{_output_prefix}.txt'
    logger.info(f"Processing audio files: {audio_files}. Output file prefix: {_output_prefix}. Transcription output file: {transcript_filename}")
    try:
        record_ids = []
        responses = []    
        logger.info(f"Processing audio files: {audio_files}")
        for num, audio_filename in enumerate(audio_files):
            # Step 2: Transcribe Audio (speech to text)
            # If multiple audio files are provided, append the transcription to the same file - the first file will overwrite older file if exists
            try:
                transcript_len = transciber.transcribe(audio_file=audio_filename, transcription_output_file=transcript_filename, append= (num > 0))
                if transcript_len == 0:
                    logger.error(f"Error occurred while transcribing audio file {audio_filename}")
            except Exception as e:
                logger.log_exception(f"Error occurred while transcribing audio file {audio_filename}", e)


        # Step 3: Convert transcription to EMR record for all tables
        for table_name in tables:
            chart_name = table_name.replace(" ", "_")
            chart_filename = f'{SpeakcareEnv.get_charts_dir()}/{_output_prefix}-chart-{chart_name}.json'

            transcript = boto3Session.get_s3_or_local_file_content(transcript_filename)           
            if not transcript:
                err = f"Failed to read transcript file {transcript}"
                logger.error(err)
                raise Exception(err)

            logger.info(f"Calling create_chart_completion for table {table_name} input_file {transcript_filename}")
            response_dict = create_chart_completion(transcript=transcript, emr_table_name=table_name)
            if not response_dict:
                err = "Error occurred while converting transcription to chart."
                logger.error(err)
                raise Exception(err)
            
            responses.append(response_dict)
            if update_emr:
                # Step 4: Add transcript to EMR
                transcript_id, err = EmrUtils.add_transcript(transcript)
                if not transcript_id:
                    logger.error(f"Failed to create transcript: {err}")
                    raise Exception(err)

                # Step 5: Create EMR record
                record_id, record_state = EmrUtils.create_and_commit_emr_record(record=response_dict, transcript_id=transcript_id)
                if not record_id:
                    err = f"Failed to create EMR record for table {table_name}. from data {response_dict}"
                    logger.error(err)
                    raise Exception(err)

                record_ids.append(record_id)
                logger.info(f"Speakcare converted transctiption to table {table_name}. EMR record created: {record_id}")
        
        return record_ids, responses, {"message": "Success"}

    except Exception as e:
        logger.error(f"Error occurred while processing audio: {e}")
        return None, None, {"error": str(e)}


def speakcare_demo_record_and_process_audio(tables: List[str], output_file_prefix:str="output", recording_duration:int=30, audio_device:int =None, dryrun: bool=False):
    """
    Full Speakcare pipeline: Record audio, transcribe audio, convert transcription to EMR record
    """    
    # prepare file names
    recording_filename = f'{SpeakcareEnv.get_audio_local_dir()}/{output_file_prefix}.wav'

    try:
        # Step 1: Record Audio
        logger.info(f"Recording audio from device index {audio_device} for {recording_duration} seconds into {recording_filename}")
        recording = audio_record(device_index=audio_device, duration=recording_duration, output_filename=recording_filename)
        if recording == 0:
            err="Error occurred while recording audio."
            logger.error(err)
            raise Exception(err)
        # Step 2: Transcribe Audio (speech to text)
        return speakcare_demo_process_audio(audio_files=[recording_filename], output_file_prefix=output_file_prefix, tables=tables, dryrun=dryrun)
    
    except Exception as e:
        logger.error(f"Error occurred while processing audio: {e}")
        return None, {"error": str(e)}


