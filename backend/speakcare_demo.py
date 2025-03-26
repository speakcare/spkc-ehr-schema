#!/usr/bin/env python3

import argparse
from dotenv import load_dotenv
from typing import List
import os
# from speakcare_audio import record_audio, audio_check_input_device, audio_print_input_devices, audio_get_devices_string
from speakcare_logging import SpeakcareLogger
from speakcare_stt import SpeakcareOpenAIWhisper
from speakcare_charting import create_chart_completion
from speakcare_emr_utils import EmrUtils
from boto3_session import Boto3Session
from speakcare_env import SpeakcareEnv
from speakcare_audio import audio_convert_to_wav, audio_is_wav, audio_is_webm
from os_utils import os_get_filename_without_ext, os_concat_current_time
from speakcare_audio import audio_record

load_dotenv()
DB_DIRECTORY = os.getenv("DB_DIRECTORY", "db")

logger = SpeakcareLogger(__name__)

SpeakcareEnv.load_env()
boto3Session = Boto3Session.get_single_instance()

supported_tables = EmrUtils.get_table_names()
transciber = SpeakcareOpenAIWhisper()

def speakcare_demo_process_audio(audio_files: List[str], tables: List[str], output_file_prefix:str=None, dryrun: bool=False):
    """
    Transcribe audio, convert transcription to EMR record
    """    
    # prepare file names
    # use output_file_prefix if provided, otherwise use the basename of the first audio file
    _output_prefix = output_file_prefix if output_file_prefix\
                          else os_concat_current_time(os_get_filename_without_ext(audio_files[0]))

    transcription_filename = f'{SpeakcareEnv.get_texts_local_dir()}/{_output_prefix}.txt'
    logger.info(f"Processing audio files: {audio_files}. Output file prefix: {_output_prefix}. Transcription output file: {transcription_filename}")
    try:
        record_ids = []    
        logger.info(f"Processing audio files: {audio_files}")
        for num, audio_filename in enumerate(audio_files):
            # Step 2: Transcribe Audio (speech to text)
            # If multiple audio files are provided, append the transcription to the same file - the first file will overwrite older file if exists
            try:
                transcript_len = transciber.transcribe(audio_file=audio_filename, transcription_output_file=transcription_filename, append= (num > 0))
                if transcript_len == 0:
                    logger.error(f"Error occurred while transcribing audio file {audio_filename}")
            except Exception as e:
                logger.log_exception(f"Error occurred while transcribing audio file {audio_filename}", e)


        # Step 3: Convert transcription to EMR record for all tables
        for table_name in tables:
            chart_name = table_name.replace(" ", "_")
            chart_filename = f'{SpeakcareEnv.get_charts_dir()}/{_output_prefix}-chart-{chart_name}.json'

            logger.info(f"Calling create_chart_completion for table {table_name} input_file {transcription_filename} output_file {chart_filename}")
            record_id = create_chart_completion(boto3Session=boto3Session, input_file=transcription_filename, output_file=chart_filename, 
                                                emr_table_name=table_name, dryrun=dryrun)
            if not record_id:
                err = "Error occurred while converting transcription to EMR record."
                logger.error(err)
                raise Exception(err)
                        
            record_ids.append(record_id)
            logger.info(f"Speakcare converted transctiption to table {table_name}. EMR record created: {record_id}")
        
        return record_ids, {"message": "Success"}

    except Exception as e:
        logger.error(f"Error occurred while processing audio: {e}")
        return None, {"error": str(e)}


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


