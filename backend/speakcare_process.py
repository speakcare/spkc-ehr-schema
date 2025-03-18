#!/usr/bin/env python3

import argparse
import random
from datetime import datetime, timezone
from dotenv import load_dotenv
from typing import List
import os
from speakcare_audio import record_audio, audio_check_input_device, audio_print_input_devices, audio_get_devices_string
from speakcare_logging import SpeakcareLogger
from speakcare_stt import SpeakcareOpenAIWhisper
from speakcare_diarize import SpeakcareDiarize
from speakcare_charting import create_chart_completion
from speakcare_emr import SpeakCareEmr
from speakcare_emr_utils import EmrUtils
from boto3_session import Boto3Session
from speakcare_env import SpeakcareEnv
from speakcare_audio import audio_convert_to_wav, audio_is_wav
from os_utils import os_ensure_file_directory_exists, os_get_file_extension, os_get_filename_without_ext, os_concat_current_time

load_dotenv()
DB_DIRECTORY = os.getenv("DB_DIRECTORY", "db")


logger = SpeakcareLogger(__name__)



SpeakcareEnv.load_env()
boto3Session = Boto3Session.get_single_instance()

supported_tables = EmrUtils.get_table_names()
diarizer = SpeakcareDiarize()
transciber = SpeakcareOpenAIWhisper()


def speakcare_process_audio(audio_files: List[str], tables: List[str], output_file_prefix:str=None, dryrun: bool=False):
    """
    Transcribe audio, convert transcription to EMR record
    """    
    # prepare file names
    # use output_file_prefix if provided, otherwise use the basename of the first audio file
    _output_prefix = output_file_prefix if output_file_prefix\
                          else os_concat_current_time(os_get_filename_without_ext(audio_files[0]))

    transcription_filename = f'{SpeakcareEnv.get_texts_dir()}/{_output_prefix}.txt'
    logger.info(f"Processing audio files: {audio_files}. Output file prefix: {_output_prefix}. Transcription output file: {transcription_filename}")
    audio_local_file = None
    is_s3_file = False
    try:
        record_ids = []    
        logger.info(f"Processing audio files: {audio_files}")
        for num, audio_filename in enumerate(audio_files):
            audio_local_file, remove_local_file = boto3Session.s3_localize_file(audio_filename)
            # Step 1: Verify the audio file exists
            if not audio_local_file:
                err = f"Error occurred while localizing audio file {audio_filename}"
                logger.error(err)
                raise Exception(err)            

            # if audio file is not wav, convert to wav
            if not audio_is_wav(audio_local_file): #audio_local_file.endswith(".wav"):
                wav_filename = audio_convert_to_wav(audio_local_file)
            else:
                wav_filename = audio_local_file
            
            # Step 2: Transcribe Audio (speech to text)
            # If multiple audio files are provided, append the transcription to the same file - the first file will overwrite older file if exists
            try:
                transcript_len = diarizer.diarize(audio_file=wav_filename, output_file=transcription_filename, append= (num > 0))
                if transcript_len == 0:
                    logger.error(f"Error occurred while transcribing audio file {wav_filename}")
            except Exception as e:
                logger.log_exception(f"Error occurred while transcribing audio file {wav_filename}", e)
            finally:
                if wav_filename != audio_local_file:
                    # delete the converted wav file
                    os.remove(wav_filename)
                    logger.info(f"Deleted converted wav file {wav_filename}")

                if remove_local_file:
                    # delete the local audio file                
                    if audio_local_file and os.path.isfile(audio_local_file):
                        os.remove(audio_local_file)
                        logger.info(f"Deleted local audio file {audio_local_file}")

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
    
def speakcare_process_audio_demo(audio_files: List[str], tables: List[str], output_file_prefix:str=None, dryrun: bool=False):
    """
    Transcribe audio, convert transcription to EMR record
    """    
    # prepare file names
    # use output_file_prefix if provided, otherwise use the basename of the first audio file
    _output_prefix = output_file_prefix if output_file_prefix\
                          else os_concat_current_time(os_get_filename_without_ext(audio_files[0]))

    transcription_filename = f'{SpeakcareEnv.get_texts_dir()}/{_output_prefix}.txt'
    logger.info(f"Processing audio files: {audio_files}. Output file prefix: {_output_prefix}. Transcription output file: {transcription_filename}")
    audio_local_file = None
    is_s3_file = False
    try:
        record_ids = []    
        logger.info(f"Processing audio files: {audio_files}")
        for num, audio_filename in enumerate(audio_files):
            audio_local_file, remove_local_file = boto3Session.s3_localize_file(audio_filename)
            # Step 1: Verify the audio file exists
            if not audio_local_file:
                err = f"Error occurred while localizing audio file {audio_filename}"
                logger.error(err)
                raise Exception(err)            

            # if audio file is not wav, convert to wav
            if not audio_is_wav(audio_local_file): #audio_local_file.endswith(".wav"):
                wav_filename = audio_convert_to_wav(audio_local_file)
            else:
                wav_filename = audio_local_file
            
            # Step 2: Transcribe Audio (speech to text)
            # If multiple audio files are provided, append the transcription to the same file - the first file will overwrite older file if exists
            try:
                #transcript_len = diarizer.diarize(audio_file=wav_filename, output_file=transcription_filename, append= (num > 0))
                transcript_len = transciber.transcribe(audio_file=wav_filename, transcription_output_file=transcription_filename, append= (num > 0))
                if transcript_len == 0:
                    logger.error(f"Error occurred while transcribing audio file {wav_filename}")
            except Exception as e:
                logger.log_exception(f"Error occurred while transcribing audio file {wav_filename}", e)
            finally:
                if wav_filename != audio_local_file:
                    # delete the converted wav file
                    os.remove(wav_filename)
                    logger.info(f"Deleted converted wav file {wav_filename}")

                if remove_local_file:
                    # delete the local audio file                
                    if audio_local_file and os.path.isfile(audio_local_file):
                        os.remove(audio_local_file)
                        logger.info(f"Deleted local audio file {audio_local_file}")

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


def speakcare_process_transcription(diarization_filename: str, tables: List[str], output_file_prefix:str, dryrun: bool=False):
    """
    Transcribe audio, convert transcription to EMR record
    """    
    # prepare file names
    # use output_file_prefix if provided, otherwise use the basename of the first audio file

    logger.info(f"Processing diarized transcription file {diarization_filename}. Output file prefix: {output_file_prefix}.")
    try:
        record_ids = []    
        for table_name in tables:
            chart_name = table_name.replace(" ", "_")
            chart_filename = f'{SpeakcareEnv.get_charts_dir()}/{output_file_prefix}-chart-{chart_name}.json'            
            logger.info(f"Calling create_chart_completion for table {table_name} input_file {diarization_filename} output_file {chart_filename}")
            record_id = create_chart_completion(boto3Session=boto3Session, input_file=diarization_filename, output_file=chart_filename, 
                                            emr_table_name=table_name, dryrun=dryrun)
            
            if not record_id:
                err = f"Error occurred while converting diarized transcription '{diarization_filename}' to EMR record."
                logger.error(err)
                raise Exception(err)
                        
            record_ids.append(record_id)
            logger.info(f"Speakcare converted transctiption to table {table_name}. EMR record created: {record_id}")
        
        return record_ids, {"message": "Success"}

    except Exception as e:
        logger.error(f"Error occurred while processing audio: {e}")
        return None, {"error": str(e)}    


def speakcare_record_and_process_audio(tables: List[str], output_file_prefix:str="output", recording_duration:int=30, audio_device:int =None, dryrun: bool=False):
    """
    Full Speakcare pipeline: Record audio, transcribe audio, convert transcription to EMR record
    """    
    # prepare file names
    recording_filename = f'{SpeakcareEnv.get_audio_local_dir()}/{output_file_prefix}.wav'

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
    parser = argparse.ArgumentParser(description='Speakcare speech to EMR.')
    # Add arguments
    parser.add_argument('-l', '--list-devices', action='store_true',
                        help='Print input devices list and exit')
    parser.add_argument('-o', '--output-prefix', type=str,
                        help='Output file prefix (default: the basename of the first input recording file)')
    parser.add_argument('-c', '--chart', type=str, nargs='+',
                        help=f'Chart (table) names (supported charts: {supported_tables})')
    parser.add_argument('-ne', '--no-emr', action='store_true',
                        help='If no-emr, write JSON only and do not udpate the EMR')
    parser.add_argument('-r', '--input-recording', nargs='+', type=str,
                        help='Name of input recording files to process. If provided, we skip the recording and use these files instead.')
    parser.add_argument('-s', '--seconds', type=int, default=30,
                        help='Recording duration in seconds (default: 30)')
    parser.add_argument('-a', '--audio-device', type=int,
                        help='Audio device index (required if recording is needed)')
    parser.add_argument('-d', '--diarization', type=str, 
                        help='Name of diarization file to process. If provided, we skip the recording and use these files instead.')

    # Parse arguments
    args = parser.parse_args()

    EmrUtils.init_db(db_directory=DB_DIRECTORY, create_db=True)
    SpeakcareEnv.load_env()


    if args.list_devices:
        audio_print_input_devices()
        exit(0)

    # Ensure --table is always provided if --list-devices is not used
    if not args.chart:
        parser.error("--chart is required.")
 
    table_names = args.chart
    unsupported_tables = [table for table in table_names if table not in supported_tables]
    if unsupported_tables:
        parser.error(f"Invalid chart names: {unsupported_tables}. Supported charts: {supported_tables}")

    output_file_prefix = "output"

    dryrun = args.no_emr
    if dryrun:
        logger.info("No EMR mode. EMR record will not be created.")

    if args.diarization:
        diarization_filename = args.diarization
        output_file_prefix = os_get_filename_without_ext(diarization_filename)
        record_ids, error = speakcare_process_transcription(diarization_filename=diarization_filename, tables=table_names, output_file_prefix=output_file_prefix, dryrun=dryrun)
        EmrUtils.cleanup_db(delete_db_files=False)
        exit(0)


    input_recordings = args.input_recording
    if args.output_prefix:
        output_file_prefix = args.output_prefix
    elif input_recordings:
        # get the file basename of the first file in the input recording list, without the extension
        output_file_prefix = os_get_filename_without_ext(input_recordings[0])

    output_file_prefix = os_concat_current_time(output_file_prefix)

    
    if args.input_recording:
        # Process the provided audio file and exit
        record_ids, error = speakcare_process_audio(audio_files=input_recordings, output_file_prefix=output_file_prefix, tables=table_names, dryrun=dryrun)
        EmrUtils.cleanup_db(delete_db_files=False)
        exit(0)


    # If --input-recording is not provided, then --audio-device is required
    if args.audio_device is None:
        parser.error("--audio-device is required when recording audio")
    
    audio_device = args.audio_device
    if not audio_check_input_device(audio_device):
        parser.error(f"Invalid audio device index: {audio_device}. Please provide a valid device index: \n{audio_get_devices_string()}")
 
    recording_duration = 30
    if args.seconds:
        recording_duration = args.seconds

    
    speakcare_record_and_process_audio(tables=table_names, output_file_prefix=output_file_prefix, recording_duration=recording_duration, audio_device=audio_device, dryrun=dryrun)
    EmrUtils.cleanup_db(delete_db_files=False)

if __name__ == "__main__":
    main()
    print("Speakcare completed  ...")