#This reads text sessions and converts them into structured data records.
from models import Transcripts, MedicalRecords, TranscriptState, TranscriptsDBSession, MedicalRecordsDBSession
from speakcare_emr_utils import EmrUtils
from speakcare_logging import create_logger
import time
import argparse
import signal
import sys

logger = create_logger(__name__)


def process_new_transcripts():
    # Create sessions for interacting with the database
    num_transcripts_processed = 0
    num_records_created = 0
    transcript_session = TranscriptsDBSession()
    medical_records_session = MedicalRecordsDBSession()

    # Fetch new, unprocessed transcripts
    new_transcripts = EmrUtils.get_all_transcripts(text_limit=64, state=TranscriptState.NEW)

    for transcript in new_transcripts:
        # Convert the raw text into structured data (placeholder for conversion logic)
        structured_data = {
            'key1': 'value1',  # Example transformation
            # Implement the actual transformation logic here
        }

        # Add the structured data to the medical records store
        new_record = MedicalRecords(
            data=structured_data, 
            metadata={'source_transcript_id': transcript.id}, 
            state='new'
        )
        medical_records_session.add(new_record)

        # Mark the transcript as processed
        transcript.processed = True
        transcript_session.commit()
        medical_records_session.commit()

    logger.info(f"Processed {num_transcripts_processed} transcripts and created {num_records_created} medical records.")
    return num_transcripts_processed, num_records_created

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run process_new_transcripts in an infinite loop.')
    parser.add_argument('-s', '--sleep', type=int, default=5, help='Number of seconds to sleep between each call to process_new_transcripts (default: 5)')
    parser.add_argument('-o', '--once', action='store_true', help='Run process_new_transcripts only once')
    args = parser.parse_args()
    
    sleep = args.sleep
    run_once = args.once

    def signal_handler(sig, frame):
        logger.info('Interrupted. Exiting gracefully...')
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Infinite loop to call process_new_transcripts and sleep for K seconds
    while True:
        try:
            num_transcripts, num_records = process_new_transcripts()
            logger.debug(f"process_new_transcripts: {num_transcripts} transcripts and created {num_records} medical records.")
        except Exception as e:
            print(f"Error occurred while processing transcripts: {e}")
        
        if run_once:
            break
        
        print(f"Sleeping for {sleep} seconds...")
        time.sleep(sleep)

if __name__ == '__main__':
    main()
