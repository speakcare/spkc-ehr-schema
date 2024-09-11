#This reads text sessions and converts them into structured data records.
from models import Transcripts, MedicalRecords, TranscriptsDBSession, MedicalRecordsDBSession

def process_new_transcripts():
    # Create sessions for interacting with the databases
    transcript_session = TranscriptsDBSession()
    medical_records_session = MedicalRecordsDBSession()

    # Fetch new, unprocessed transcripts
    new_transcripts = transcript_session.query(Transcripts).filter_by(processed=False).all()

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

if __name__ == '__main__':
    process_new_transcripts()