import argparse
from os_utils import ensure_directory_exists
from datetime import datetime, timezone
from speakcare_audio import record_audio, print_audio_devices
from speakcare_logging import create_logger
from speakcare_stt import transcribe_audio
from speakcare_transcriptions import transciption_to_emr
from speakcare_emr import SpeakCareEmr


def speakcare():
    logger = create_logger(__name__)
    output_root_dir = "out"
    recordings_dir = f"{output_root_dir}/recordings"
    transciptions_dir = f"{output_root_dir}/transcriptions"
    jsons_dir = f"{output_root_dir}/jsons"
    ensure_directory_exists(recordings_dir)
    ensure_directory_exists(transciptions_dir)
    ensure_directory_exists(jsons_dir)

    supported_tables = [SpeakCareEmr.BLOOD_PRESSURES_TABLE, 
                        SpeakCareEmr.WEIGHTS_TABLE, 
                        SpeakCareEmr.ADMISSION_TABLE,
                        SpeakCareEmr.TEMPERATURES_TABLE]

    parser = argparse.ArgumentParser(description='Audio input recorder.')
    parser.add_argument('-l', '--list', action='store_true', help='Print devices list and exit')
    parser.add_argument('-s', '--seconds', type=int, default=30, help='Recording duration (default: 30)')
    parser.add_argument('-o', '--output-prefix', type=str, default="output", help='Output file prefix (default: output)')
    parser.add_argument('-t', '--table', type=str, required=True, help=f'Table name (suported tables: {supported_tables}')
    parser.add_argument('-d', '--dryrun', action='store_true', help=f'If dryrun write JSON only and do not create EMR record')
    parser.add_argument('-a', '--audio-device', type=int, default=-1, help='Audio device index (required)')

    args = parser.parse_args()

    if args.list:
        print_audio_devices()
        exit(0)

    output_file_prefix = "output"
    if args.output_prefix:
        output_file_prefix = args.output_prefix
    
    recording_duration = 30
    if args.seconds:
        recording_duration = args.seconds

    audio_device = args.audio_device
    if (audio_device := args.audio_device) == -1:
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
    
    # prepare file names
    # Get the current UTC time
    utc_now = datetime.now(timezone.utc)
    # Format the datetime as a string without microseconds and timezone
    utc_string = utc_now.strftime('%Y-%m-%dT%H:%M:%S')

    recording_filename = f'{recordings_dir}/{output_file_prefix}.{utc_string}.wav'
    transcription_filename = f'{transciptions_dir}/{output_file_prefix}.{utc_string}.txt'
    json_filename = f'{jsons_dir}/{output_file_prefix}.{utc_string}.json'


    # Step 1: Record Audio
    logger.info(f"Recording audio from device index {audio_device} for {recording_duration} seconds into {recording_filename}")
    recording = record_audio(duration=recording_duration, output_filename=recording_filename)
    if recording == 0:
        logger.error(f"Error occurred while recording audio.")
        exit(1)
    # Step 2: Transcribe Audio (speech to text)
    transcription = transcribe_audio(input_file=recording_filename, output_file=transcription_filename)
    if transcription == 0:
        logger.error(f"Error occurred while transcribing audio.")
        exit(1)

    # Step 3: Convert transcription to EMR record
    record_id = transciption_to_emr(input_file=transcription_filename, output_file=json_filename, 
                                    table_name=table_name, dryrun=dryrun)
    if not record_id:
        logger.error(f"Error occurred while converting transcription to EMR record.")
        exit(1)
    # Step 2: Transcribe Audio
    
    logger.info(f"Speakcare completed. EMR record created: {record_id}")