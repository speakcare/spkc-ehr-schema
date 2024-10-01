#!/usr/bin/env python3

import argparse
from datetime import datetime, timezone
from dotenv import load_dotenv
import os
from os_utils import ensure_directory_exists
from speakcare_audio import record_audio, print_audio_devices, check_input_device, print_input_devices
from speakcare_logging import create_logger
from speakcare_stt import transcribe_audio
from speakcare_transcriptions import transcription_to_emr
from speakcare_emr import SpeakCareEmr
from models import init_speakcare_db
from speakcare_emr_utils import EmrUtils

load_dotenv()
DB_DIRECTORY = os.getenv("DB_DIRECTORY", "db")

logger = create_logger(__name__)
output_root_dir = "out"
recordings_dir = f"{output_root_dir}/recordings"
transciptions_dir = f"{output_root_dir}/transcriptions"
jsons_dir = f"{output_root_dir}/jsons"

supported_tables = [SpeakCareEmr.BLOOD_PRESSURES_TABLE, 
                    SpeakCareEmr.WEIGHTS_TABLE, 
                    SpeakCareEmr.ADMISSION_TABLE,
                    SpeakCareEmr.TEMPERATURES_TABLE,
                    SpeakCareEmr.PULSES_TABLE]

def get_supported_tables():
    return supported_tables

def speakcare_process_audio(output_file_prefix="output", recording_duration=30, table_name=None, audio_device=None, dryrun=False):
    """
    Full Speakcare pipeline: Record audio, transcribe audio, convert transcription to EMR record
    """    
    # prepare file names
    # Get the current UTC time
    utc_now = datetime.now(timezone.utc)
    # Format the datetime as a string without microseconds and timezone
    utc_string = utc_now.strftime('%Y-%m-%dT%H:%M:%S')

    recording_filename = f'{recordings_dir}/{output_file_prefix}.{utc_string}.wav'
    transcription_filename = f'{transciptions_dir}/{output_file_prefix}.{utc_string}.txt'
    json_filename = f'{jsons_dir}/{output_file_prefix}.{utc_string}.json'

    try:
        # Step 1: Record Audio
        logger.info(f"Recording audio from device index {audio_device} for {recording_duration} seconds into {recording_filename}")
        recording = record_audio(device_index=audio_device, duration=recording_duration, output_filename=recording_filename)
        if recording == 0:
            err="Error occurred while recording audio."
            logger.error(err)
            raise Exception(err)
        # Step 2: Transcribe Audio (speech to text)
        transcription = transcribe_audio(input_file=recording_filename, output_file=transcription_filename)
        if transcription == 0:
            err = "Error occurred while transcribing audio."
            logger.error(err)
            raise Exception(err)

        # Step 3: Convert transcription to EMR record
        record_id = transcription_to_emr(input_file=transcription_filename, output_file=json_filename, 
                                        table_name=table_name, dryrun=dryrun)
        if not record_id:
            err = "Error occurred while converting transcription to EMR record."
            logger.error(err)
            raise Exception(err)
        # Step 2: Transcribe Audio
        
        logger.info(f"Speakcare completed. EMR record created: {record_id}")
        return record_id, ""

    except Exception as e:
        logger.error(f"Error occurred while processing audio: {e}")
        return None, {"error": str(e)}



def main():
    # for testing from command line
    ensure_directory_exists(recordings_dir)
    ensure_directory_exists(transciptions_dir)
    ensure_directory_exists(jsons_dir)
    EmrUtils.init_db(db_directory=DB_DIRECTORY)

    list_parser = argparse.ArgumentParser(description='Speakcare speech to EMR.', add_help=False)
    list_parser.add_argument('-l', '--list-devices', action='store_true', help='Print input devices list and exit')
    args, remaining_args = list_parser.parse_known_args()
    if args.list_devices:
        print_input_devices()
        exit(0)

    full_parser = argparse.ArgumentParser(description='Speakcare speech to EMR.', parents=[list_parser])
    full_parser.add_argument('-s', '--seconds', type=int, default=30, help='Recording duration (default: 30)')
    full_parser.add_argument('-o', '--output-prefix', type=str, default="output", help='Output file prefix (default: output)')
    full_parser.add_argument('-t', '--table', type=str, required=True, help=f'Table name (suported tables: {supported_tables}')
    full_parser.add_argument('-d', '--dryrun', action='store_true', help=f'If dryrun write JSON only and do not create EMR record')
    full_parser.add_argument('-a', '--audio-device', type=int, required=True, help='Audio device index (required)')

    args = full_parser.parse_args()

    output_file_prefix = "output"
    if args.output_prefix:
        output_file_prefix = args.output_prefix
    
    recording_duration = 30
    if args.seconds:
        recording_duration = args.seconds

    audio_device = args.audio_device
    if not check_input_device(audio_device):
        print("Please provide a valid device index (-a | --audio-device) to record audio.")
        print_audio_devices()
        exit(1)
    
    
    table_name = args.table
    if table_name not in supported_tables:
        logger.error(f"Invalid table name: {table_name}. Supported tables: {supported_tables}")
        exit(1)
    
    dryrun = args.dryrun
    if dryrun:
        logger.info("Dryrun mode enabled. EMR record will not be created.")

    speakcare_process_audio(output_file_prefix=output_file_prefix, recording_duration=recording_duration, table_name=table_name, audio_device=audio_device, dryrun=dryrun)
    EmrUtils.cleanup_db(delete_db_files=False)

if __name__ == "__main__":
    main()
    print("Speakcare completed  ...")