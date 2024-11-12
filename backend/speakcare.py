#!/usr/bin/env python3

import argparse
import random
from datetime import datetime, timezone
from dotenv import load_dotenv
from typing import List
import os
from os_utils import ensure_directory_exists
from speakcare_audio import record_audio, check_input_device, print_input_devices, get_audio_devices_string
from speakcare_logging import SpeakcareLogger
from speakcare_stt import transcribe_audio
from speakcare_transcriptions import transcription_to_emr
from speakcare_emr import SpeakCareEmr
from speakcare_emr_utils import EmrUtils

load_dotenv()
DB_DIRECTORY = os.getenv("DB_DIRECTORY", "db")

logger = SpeakcareLogger(__name__)
output_root_dir = "out"
recordings_dir = f"{output_root_dir}/recordings"
ensure_directory_exists(recordings_dir)
transciptions_dir = f"{output_root_dir}/transcriptions"
ensure_directory_exists(transciptions_dir)
jsons_dir = f"{output_root_dir}/jsons"
ensure_directory_exists(jsons_dir)

supported_tables = EmrUtils.get_table_names()


def speakcare_process_audio(audio_files: List[str], tables: List[str], output_file_prefix:str="output", dryrun: bool=False):
    """
    Transcribe audio, convert transcription to EMR record
    """    
    # prepare file names

    rnd = random.randint(1000, 9999)
    transcription_filename = f'{transciptions_dir}/{output_file_prefix}_{rnd}.txt'
    json_filename = f'{jsons_dir}/{output_file_prefix}_{rnd}.json'


    try:
        record_ids = []    
        for num, audio_filename in enumerate(audio_files):
            # Step 1: Verify the audio file exists
            if not os.path.isfile(audio_filename):
                err = f"Audio file not found or not file type: {audio_filename}"
                logger.error(err)
                raise Exception(err)
            
            # Step 2: Transcribe Audio (speech to text)
            # If multiple audio files are provided, append the transcription to the same file - the first file will overwrite older file if exists
            transcript_len = transcribe_audio(input_file=audio_filename, output_file=transcription_filename, append= (num > 0))
            if transcript_len == 0:
                err = "Error occurred while transcribing audio."
                logger.error(err)
                raise Exception(err)

        # Step 3: Convert transcription to EMR record for all tables
        for table_name in tables:
            record_id = transcription_to_emr(input_file=transcription_filename, output_file=json_filename, 
                                            table_name=table_name, dryrun=dryrun)
            if not record_id:
                err = "Error occurred while converting transcription to EMR record."
                logger.error(err)
                raise Exception(err)
                        
            record_ids.append(record_id)
            logger.info(f"Speakcare converted transctiption to table {table_name}. EMR record created: {record_id}")
        
        return record_ids, ""

    except Exception as e:
        logger.error(f"Error occurred while processing audio: {e}")
        return None, {"error": str(e)}


def speakcare_record_and_process_audio(tables: List[str], output_file_prefix:str="output", recording_duration:int=30, audio_device:int =None, dryrun: bool=False):
    """
    Full Speakcare pipeline: Record audio, transcribe audio, convert transcription to EMR record
    """    
    # prepare file names
    recording_filename = f'{recordings_dir}/{output_file_prefix}.wav'

    try:
        # Step 1: Record Audio
        logger.info(f"Recording audio from device index {audio_device} for {recording_duration} seconds into {recording_filename}")
        recording = record_audio(device_index=audio_device, duration=recording_duration, output_filename=recording_filename)
        if recording == 0:
            err="Error occurred while recording audio."
            logger.error(err)
            raise Exception(err)
        # Step 2: Transcribe Audio (speech to text)
        return speakcare_process_audio(audio_files=[recording_filename], output_file_prefix=output_file_prefix, tables=tables, dryrun=dryrun)
    
    except Exception as e:
        logger.error(f"Error occurred while processing audio: {e}")
        return None, {"error": str(e)}



def main():
    # for testing from command line
    ensure_directory_exists(recordings_dir)
    ensure_directory_exists(transciptions_dir)
    ensure_directory_exists(jsons_dir)
    EmrUtils.init_db(db_directory=DB_DIRECTORY, create_db=True)

    parser = argparse.ArgumentParser(description='Speakcare speech to EMR.')
    # Add arguments
    parser.add_argument('-l', '--list-devices', action='store_true',
                        help='Print input devices list and exit')
    parser.add_argument('-o', '--output-prefix', type=str, default="output",
                        help='Output file prefix (default: output)')
    parser.add_argument('-t', '--table', type=str, nargs='+',
                        help=f'Table names (supported tables: {supported_tables})')
    parser.add_argument('-d', '--dryrun', action='store_true',
                        help='If dryrun, write JSON only and do not create EMR record')
    parser.add_argument('-i', '--input-recording', nargs='+', type=str,
                        help='Name of input recording files to process. If provided, we skip the recording and use these files instead.')
    parser.add_argument('-s', '--seconds', type=int, default=30,
                        help='Recording duration in seconds (default: 30)')
    parser.add_argument('-a', '--audio-device', type=int,
                        help='Audio device index (required if recording is needed)')

    # Parse arguments
    args = parser.parse_args()

    if args.list_devices:
        print_input_devices()
        exit(0)

    # Ensure --table is always provided if --list-devices is not used
    if not args.table:
        parser.error("--table is required.")
 
    table_names = args.table
    unsupported_tables = [table for table in table_names if table not in supported_tables]
    if unsupported_tables:
        parser.error(f"Invalid table names: {unsupported_tables}. Supported tables: {supported_tables}")
    # if table_name not in supported_tables:
    #     parser.error(f"Invalid table name: {table_name}. Supported tables: {supported_tables}")


    output_file_prefix = "output"
    if args.output_prefix:
        output_file_prefix = args.output_prefix

    dryrun = args.dryrun
    if dryrun:
        logger.info("Dryrun mode enabled. EMR record will not be created.")

    utc_now = datetime.now(timezone.utc)
    # Format the datetime as a string without microseconds and timezone
    utc_string = utc_now.strftime('%Y-%m-%dT%H:%M:%S')
    output_file_prefix = f'{output_file_prefix}.{utc_string}'

    if args.input_recording:
        # Process the provided audio file and exit
        record_ids, error = speakcare_process_audio(audio_files=args.input_recording, output_file_prefix=output_file_prefix, tables=table_names, dryrun=dryrun)
        EmrUtils.cleanup_db(delete_db_files=False)
        exit(0)


    # If --input-recording is not provided, then --audio-device is required
    if args.audio_device is None:
        parser.error("--audio-device is required when recording audio")
    
    audio_device = args.audio_device
    if not check_input_device(audio_device):
        parser.error(f"Invalid audio device index: {audio_device}. Please provide a valid device index: \n{get_audio_devices_string()}")
 
    recording_duration = 30
    if args.seconds:
        recording_duration = args.seconds

    
    speakcare_record_and_process_audio(tables=table_names, output_file_prefix=output_file_prefix, recording_duration=recording_duration, audio_device=audio_device, dryrun=dryrun)
    EmrUtils.cleanup_db(delete_db_files=False)

if __name__ == "__main__":
    main()
    print("Speakcare completed  ...")