from datetime import datetime
from speakcare_emr_api import SpeakCareEmrApi
import logging
from config import SpeakCareEmrApiconfig
from speakcare_emr_api import get_emr_api_instance
from models import MedicalRecords, Transcripts, RecordType, RecordState
from sqlalchemy.orm import sessionmaker, Session

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
    foundName, patientId, patientEmrId = emr_api.lookup_patient(name)

    if not patientEmrId:
        return None

    emr_patient = emr_api.get_patient(patientEmrId)
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


def get_emr_table_names():
    table_names = emr_api.get_emr_table_names()
    return table_names

def get_emr_table_section_names(tableName):
    section_names = emr_api.get_emr_table_section_names(tableName)
    return section_names

def get_table_external_schema(tableName):
    table_schema = emr_api.get_table_external_schema(tableName)
    return table_schema


def create_medical_record(session: Session, data: dict):
    """
    Creates a new medical record linked to a given transcript.

    :param session: The SQLAlchemy session to use for the database operations.
    :param data: A dictionary containing the data for the medical record.
    :return: A tuple containing the new record object and an HTTP status code.
    """


    # Perform any additional validity checks on the data
    # Example: Check if the data dictionary contains necessary keys
    try:
        # first check for unrecoverable errors

        required_fields = ['type', 'table_name', 'patient_name', 'nurse_name', 'info']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

        _type = RecordType(data['type'])
        _table_name = data['table_name']
        _patient_name = data['patient_name']
        _patient_id = data.get('patient_id', None)
        _nurse_name = data['nurse_name']
        _nurse_id = data.get('nurse_id', None)
        _info = data['info']
        _transcript_id = data.get('transcript_id', None)
        _errors = []
        _state = RecordState.PENDING

        # Check if the transcript exists
        if _transcript_id is not None:
            transcript = session.query(Transcripts).get(_transcript_id)
            if not transcript:
                raise ValueError("Transcript not found")
            
        # TODO: check for validity of _type and _table_name

        # TODO: check for validity of _info data
    except ValueError as e:
        logger.error(f"Error creating medical record: {e}")
        return {"error": str(e)}, 400, None
    
    # lookup and validate patient
    foundPatient, foundPatientId = emr_api.lookup_patient(_patient_name)
    if not foundPatientId: # patient not found, this can be corrected by the user
        _state = RecordState.ERRORS
        err = f"Patient {_patient_name} not found in the EMR."
        _errors.append(err)
        logger.warning(err)
    elif _patient_id and _patient_id != foundPatientId:  # wrong patient ID, this can be corrected by the user
        _state = RecordState.ERRORS
        err = f"Patient ID {_patient_id} does not match the patient ID {foundPatientId} found in the EMR for patient {_patient_name}."
        _errors.append(err)
        logger.warning(err)
    else:
        _patient_id = foundPatientId

        
    # lookup and validate nurse
    foundNurse, foundNurseId = emr_api.lookup_nurse(_nurse_name)
    if not foundNurseId:
        _state = RecordState.ERRORS
        err = f"Nurse {_nurse_name} not found in the EMR."
        _errors.append(err)
        logger.warning(err)
    elif _nurse_id and _nurse_id != foundNurseId:
        _state = RecordState.ERRORS
        err = f"Nurse ID {_nurse_id} does not match the nurse ID {foundNurseId} found in the EMR for nurse {_nurse_name}."
        _errors.append(err)
        logger.warning(err)
    else:
        _nurse_id = foundNurseId
      
    # TODO: check data validity by table name and expectd json schema of that table
    # here I need to get the table schema from the EMR API and compare it with the info data
    # Create the new medical record

    new_record = MedicalRecords(
        type= _type,  # Convert to Enum
        table_name=_table_name,
        patient_name=_patient_name,
        patient_id= _patient_id,
        nurse_name=_nurse_name,
        nurse_id= _nurse_id,
        info= _info,
        transcript_id = _transcript_id,
        state= _state 
    )
    
    # Add and commit the new record to the database
    session.add(new_record)
    session.commit()

    return {"message": "Medical record created successfully", "id": new_record.id}, 201, new_record.id


# TODO: add update_medical_record function here and unify validity checks

def commit_record_to_ehr(record: MedicalRecords):

    # prepare to commit the record to the EMR
    try:
        # first verify that the record is a PENDING state
        if record.state != RecordState.PENDING:  # Example check to ensure the record is in a valid state to be committed
            raise ValueError(f"Record id {record.id} cannot be applied because it in '{record.state}' rather than in '{RecordState.PENDING}' state.")
        
        # then verify that we have valid patient and nurse names and set them in the record
        foundPatient, patientId, patientEmrId = emr_api.lookup_patient(record.patient_name) 
        if not patientId:
            record.errors
            raise ValueError(f"Patient {record.patient_name} not found in the EMR.")
        # update the patient name to the correct one as matched in the database
        record.patient_name = foundPatient
        
        foundNurse, nurseId, nurseEmrId = emr_api.lookup_nurse(record.nurse_name)
        if not nurseId:
            raise ValueError(f"Nurse {record.nurse_name} not found in the EMR.")
        # update the nurse name to the correct one as matched in the database
        record.nurse_name = foundNurse
        
        table_name  = record.table_name
        record_data = record.info
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
        
        # update the record state to 'COMMITTED'
        logger.info(f"Commiting record {record.id}")
        record.state = RecordState.COMMITTED
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
        if record.state != RecordState.PENDING:  # Example check to ensure the record is in a valid state to be discarded
                raise ValueError(f"Record id {record.id} cannot be applied because it in '{record.state}' rather than in '{RecordState.PENDING}' state.")

        logger.info(f"Discarding record {record.id}")
        record.state = RecordState.DISCARDED
        return {"message": f"Record {record.id} discarded successfully."}, 200
    
    except Exception as e:
        return {"error": str(e)}, 400           # Return error response and status code
    

def delete_record(session: Session, record: MedicalRecords):
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