from datetime import datetime
from speakcare_emr_api import SpeakCareEmrApi
import logging
from config import SpeakCareEmrApiconfig
from speakcare_emr_api import get_emr_api_instance
from models import MedicalRecords, Transcripts, RecordType, RecordState
from sqlalchemy.orm import sessionmaker

APP_BASE_ID = 'appRFbM7KJ2QwCDb6'
logging.basicConfig()
logger = logging.getLogger("speackcare.emr.api")
logger.setLevel(logging.INFO)
logger.propagate = True


# Initialize the EMR API singleton early in the app setup
emr_api = get_emr_api_instance(SpeakCareEmrApiconfig)

def get_patient_info(name):
    # Placeholder function to fetch patient info based on the name
    # This function should interact with your data source (e.g., a database or external API)
    # Example response (replace with actual data fetching logic)
    foundName, patientId = emr_api.lookup_patient(name)

    if not patientId:
        return None

    emr_patient = emr_api.get_patient(patientId)
    patient_data = {
        "emr_patient_id": patientId,
        "patient_id": emr_patient['fields']['PatientID'],
        "correct_name": emr_patient['fields']['FullName'],
        "date_of_birth": emr_patient['fields']['DateOfBirth'],
        "gender": emr_patient['fields']['Gender'],
        "department": emr_patient['fields']['Department'],
        "admission_date": emr_patient['fields']['Admission Date'],
        "photo" : emr_patient['fields']['Photo']
    }
    return patient_data


def commit_record_to_ehr(record: MedicalRecords):

    # prepare to commit the record to the EMR
    try:
        # first verify that the record is a new state
        if record.state != RecordState.NEW:  # Example check to ensure the record is in a valid state to be commited
            raise ValueError(f"Record id {record.id} cannot be applied because it in '{record.state}' rather than in '{RecordState.NEW}' state.")
        
        # then verify that we have valid patient and nurse names and set them in the record
        foundPatient, patientId = emr_api.lookup_patient(record.patient_name) 
        if not patientId:
            record.errors
            raise ValueError(f"Patient {record.patient_name} not found in the EMR.")
        # update the patient name to the correct one as matched in the database
        record.patient_name = foundPatient
        
        foundNurse, nurseId = emr_api.lookup_nurse(record.nurse_name)
        if not nurseId:
            raise ValueError(f"Nurse {record.nurse_name} not found in the EMR.")
        # update the nurse name to the correct one as matched in the database
        record.nurse_name = foundNurse
        
        record.data['Patient'] = [patientId]
        record.data['CreatedBy'] = [nurseId]

        table_name  = record.table_name
        record_data = record.data
        record_type = record.type
        if (record_type == RecordType.MEDICAL_RECORD):
            emr_record, url = emr_api.create_medical_record(tableName=table_name, record=record_data, patientId=patientId, nurseId=nurseId)
            if not emr_record:    
                raise ValueError(f"Failed to create medical record {record_data} in table {table_name}.")            
            else:
                # update the record with the EMR record ID and URL
                record.emr_record_id = emr_record['id']
                record.emr_url = url                

        # TODO handle Assessment and Assessment Section records
        
        # update the record state to 'COMMITED'
        logger.info(f"Commiting record {record.id}")
        record.state = RecordState.COMMITED
        return {"message": f"Record {record.id} applied successfully."}, 200
    
    except Exception as e:
      # Handle the error by adding it to the record's errors field
        errors = record.errors.get('errors', []) if record.errors else []  # Get existing errors, defaulting to an empty list
        if not isinstance(errors, list):        # Ensure it's a list
            errors = []
        errors.append(str(e))                   # Add the new error message
        record.errors = {"errors": errors}      # Update the record's errors field with the modified list
        return {"error": str(e)}, 400           # Return error response and status code
    

def discard_record(record: MedicalRecords):
    # Logic to discard the record
    try:
        if record.state != RecordState.NEW:  # Example check to ensure the record is in a valid state to be discarded
                raise ValueError(f"Record id {record.id} cannot be applied because it in '{record.state}' rather than in '{RecordState.NEW}' state.")

        logger.info(f"Discarding record {record.id}")
        record.state = RecordState.DISCARDED
        return {"message": f"Record {record.id} discarded successfully."}, 200
    
    except Exception as e:
        return {"error": str(e)}, 400           # Return error response and status code
    

def delete_record(session: sessionmaker, record: MedicalRecords):
    # Logic to permanently delete the record from the database
    logger.info(f"Deleting record {record.id}")
    session.delete(record)
    return {"message": f"Record {record.id} deleted successfully."}, 200

def check_data_integrity(data):
    # Function to check data integrity and populate errors if necessary
    # TODO - check that the data is in the correct format for the specific table type
    errors = []
    if not data.get('text'):
        errors.append('Text field is required.')
    if len(data.get('text', '')) < 10:
        errors.append('Text field must be at least 10 characters long.')
    return errors