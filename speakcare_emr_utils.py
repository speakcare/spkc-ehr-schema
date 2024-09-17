from datetime import datetime
from speakcare_emr import SpeakCareEmr
import logging
from config import SpeakCareEmrApiconfig
from speakcare_emr import get_emr_api_instance
from models import MedicalRecords, Transcripts, RecordType, RecordState, TranscriptsDBSession, MedicalRecordsDBSession
from sqlalchemy.orm import sessionmaker, Session
import sys
import json
from speakcare_logging import create_logger
from typing import Optional
import unittest
from sqlalchemy.orm.attributes import flag_modified

APP_BASE_ID = 'appRFbM7KJ2QwCDb6'

logger = create_logger('speackcare.emr.utils')

# Initialize the EMR API singleton early in the app setup
emr_api = get_emr_api_instance(SpeakCareEmrApiconfig)
if not emr_api:
    logger.error('Failed to initialize EMR API')
    raise Exception('Failed to initialize EMR API')

class EmrUtils:
    @staticmethod
    def get_patient_info(name):
        """
        get_patient_info
        """
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

    @staticmethod
    def get_table_names():
        table_names = emr_api.get_emr_table_names()
        return table_names

    @staticmethod
    def get_table_id(tableName):
        table_id = emr_api.get_table_id(tableName)
        return table_id
    
    @staticmethod
    def get_record_section_names(tableName):
        section_names = emr_api.get_emr_table_section_names(tableName)
        return section_names

    @staticmethod
    def get_record_writable_schema(tableName: str):
        """
        get_table_writable_schema 
        returns the table schema for a given table name in the EMR system.
        if there are sections in the table, it returns the schema for each section as well in a separate dictionary.
        IF there are no sections, the sections dictionary will be None.
        """
        # Get the main table schema
        main_schema = emr_api.get_record_writable_schema(tableName=tableName)

        # Retrieve section names
        sections = EmrUtils.get_record_section_names(tableName)

        # If sections exist, build a sections dictionary
        sections_schema = None
        if sections:
            sections_schema = {}
            for section in sections:
                section_schema = emr_api.get_record_writable_schema(tableName=section)
                sections_schema[section] = section_schema

        # Return main schema and sections separately
        return main_schema, sections_schema

    @staticmethod
    def validate_record(table_name: str, data: dict):
        """
        validate_record_data
        """
        return emr_api.validate_record(table_name, data)
    
    @staticmethod
    def validate_partial_record(table_name: str, data: dict):
        """
        validate_partial_record_data
        """
        return emr_api.validate_partial_record(table_name, data)

    @staticmethod
    def __record_validation_helper(table_name: str,
                                   patient_name: str,
                                   nurse_name: str,
                                   fields: dict,
                                   patient_id: str = None, 
                                   nurse_id: str = None):
        _errors =[]
        _state = RecordState.PENDING
        # validate patient
        _patient_name = patient_name
        foundPatient, foundPatientId, patientEmrId = emr_api.lookup_patient(patient_name)
        if not foundPatientId:
            _errors.append(f"Patient '{patient_name}' not found in the EMR.")
            _state = RecordState.ERRORS
        elif patient_id and patient_id != foundPatientId:
            _errors.append(f"Patient ID '{patient_id}' does not match the patient ID '{foundPatientId}' found in the EMR for patient '{patient_name}' -> '{foundPatient}'.")
            _state = RecordState.ERRORS
        else:
            _patient_name = foundPatient
            _patient_id = foundPatientId
            
        # validate nurse
        _nurse_name = nurse_name
        foundNurse, foundNurseId, nurseEmrId = emr_api.lookup_nurse(nurse_name)
        if not foundNurseId:
            _errors.append(f"Nurse '{nurse_name}' not found in the EMR.")
            _state = RecordState.ERRORS
        elif nurse_id and nurse_id != foundNurseId:
            _errors.append(f"Nurse ID '{nurse_id}' does not match the nurse ID '{foundNurseId}' found in the EMR for nurse '{nurse_name}' -> '{foundNurse}'.")
            _state = RecordState.ERRORS
        else:
            _nurse_name = foundNurse
            _nurse_id = foundNurseId

        # validate the record fields
        isValid, err = EmrUtils.validate_record(table_name, fields)
        if not isValid:
            _state = RecordState.ERRORS
            _errors.append(err)
        
        return _state, _errors, _patient_name, _patient_id, _nurse_name, _nurse_id


    @staticmethod
    def get_record(record_id: int):
        """
        Get the emr record.
        """
        try:
            session = MedicalRecordsDBSession()
            record = session.get(MedicalRecords, record_id)
            if not record:
                raise ValueError(f"Record id {record_id} not found in the database.")
            else:
                return record, None
            
        except ValueError as e:
            logger.error(f"Error getting EMR record id {record_id}: {e}")
            return None, {"error": str(e)}
        
    @staticmethod
    def get_all_records():
        """
        Get the emr record.
        """

        try:
            session = MedicalRecordsDBSession()
            records = session.query(MedicalRecords).all()
            if not records:
                raise ValueError(f"No records found in the database.")
            else:
                return records, 200
            
        except ValueError as e:
            logger.error(f"Error getting all EMR records: {e}")
            return {"error": str(e)}, 400, None



    @staticmethod
    def create_record(data: dict):
        """
        Creates a new EMR record linked to a given transcript.

        :param session: The SQLAlchemy session to use for the database operations.
        :param data: A dictionary containing the data for the medical record.
        :return: A tuple containing the a success or error message and an HTTP status code and the record id.
        """


        # Perform any additional validity checks on the data
        # Example: Check if the data dictionary contains necessary keys
        try:
            # first check for unrecoverable errors
            session = MedicalRecordsDBSession()
            required_fields = ['type', 'table_name', 'patient_name', 'nurse_name', 'fields']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

            _type = RecordType(data['type']) #automatically checked for validity by PyEnum
            _table_name = data['table_name']
            _patient_name = data['patient_name']
            _patient_id = data.get('patient_id', None)
            _nurse_name = data['nurse_name']
            _nurse_id = data.get('nurse_id', None)
            _fields = data['fields']
            _transcript_id = data.get('transcript_id', None)

            # Check if the transcript exists
            if _transcript_id is not None:
                transcript = session.query(Transcripts).get(_transcript_id)
                if not transcript:
                    raise ValueError(f"Transcript if {_transcript_id} not found")
                
            _table_id = EmrUtils.get_table_id(_table_name)
            if not _table_id:
                raise ValueError(f"Table name {_table_name} not found in the EMR.")

            # fields data integrity check is done inside the create_record function - no need to do it here
        except ValueError as e:
            logger.error(f"Error creating EMR record: {e}")
            return {"error": str(e)}, None
        
        _state, _errors, _patient_name, _patient_id, _nurse_name, _nurse_id =\
            EmrUtils.__record_validation_helper(_table_name, _patient_name, _nurse_name, _fields, _patient_id, _nurse_id)

        new_record = MedicalRecords(
            type= _type,  # Convert to Enum
            table_name=_table_name,
            patient_name=_patient_name,
            patient_id= _patient_id,
            nurse_name=_nurse_name,
            nurse_id= _nurse_id,
            fields= _fields,
            transcript_id = _transcript_id,
            state= _state,
            errors = _errors
        )
        
        # Add and commit the new record to the database
        session.add(new_record)
        session.commit()

        return {"message": "EMR record created successfully", "id": new_record.id}, new_record.id


    @staticmethod
    def update_record(updates: dict, record_id: int):
        """
        Update EMR record linked to a given transcript.

        :param session: The SQLAlchemy session to use for the database operations.
        :param data: A dictionary containing the data for the updated record.
        :param record_id: The id of the record to update.
        :return: A tuple containing the a success or error message and an HTTP status code.
        """

        try:
            # first check for unrecoverable errors
            if not updates:
                raise ValueError("The data dictionary is empt or None")
            
            session = MedicalRecordsDBSession()
            record: Optional[MedicalRecords] = session.get(MedicalRecords, record_id)
            if not record:
                raise ValueError(f"Failed to get record for record_id {record_id}")
            
            if record.state in [RecordState.COMMITTED, RecordState.DISCARDED]:
                raise ValueError(f"Record is {record_id} is in {record.state} state and cannot be changed")    
        
            # fields data integrity check is done inside the create_record function - no need to do it here
        except ValueError as e:
            logger.error(f"Error updating EMR record: {e}")
            return {"error": str(e)}, None
        
        simple_update_fields = ['patient_name', 'patient_id', 'nurse_name', 'nurse_id'] #, 'fields']
        # updae the record with the new data
        for key, value in updates.items():
            # special handling for dictionary fields
            if key == 'fields' and isinstance(value, dict):
                record.fields.update(value)
                # Explicitly mark the fields attribute as changed
                flag_modified(record, 'fields')
            elif key in simple_update_fields:
                # update the simple fields
                setattr(record, key, value)

        
        # validate the record fields and update the record state and errors after validation
        record.state, record.errors, record.patient_name, record.patient_id, record.nurse_name, record.nurse_id =\
                EmrUtils.__record_validation_helper(record.table_name, record.patient_name, record.nurse_name, record.fields, record.patient_id, record.nurse_id)
        
        # Commit the udpated record to the database
        session.commit()

        return {"message": "EMR record updated successfully", "id": record.id}, record.id

    @staticmethod
    def commit_record(record_id: int):

        # prepare to commit the record to the EMR
        try:
            session = MedicalRecordsDBSession()
            # first verify that the record is a PENDING state
            record: Optional[MedicalRecords] = session.get(MedicalRecords, record_id)
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
            record_fields = record.fields
            record_type = record.type
            if (record_type == RecordType.MEDICAL_RECORD):
                emr_record, url = emr_api.create_medical_record(tableName=table_name, record=record_fields, patientId=patientId, nurseId=nurseId)
                if not emr_record:    
                    raise ValueError(f"Failed to create medical record {record_fields} in table {table_name}.")            
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
        
    @staticmethod
    def discard_record(record_id: int):
        # Logic to discard the record
        try:
            session = MedicalRecordsDBSession()
            record: Optional[MedicalRecords] = session.get(MedicalRecords, record_id)
            if record.state == RecordState.COMMITTED:  
                    raise ValueError(f"Record id {record.id} cannot be discarded as it already COMMITTED.")

            logger.info(f"Discarding record {record.id}")
            record.state = RecordState.DISCARDED
            session.commit()
            return {"message": f"Record {record.id} discarded successfully."}, 204
        
        except Exception as e:
            return {"error": str(e)}, 400           # Return error response and status code
    
    @staticmethod
    def delete_record(record_id: int):
        # Logic to permanently delete the record from the database
        try:
            session = MedicalRecordsDBSession()
            record: Optional[MedicalRecords] = session.get(MedicalRecords, record_id)
            if not record:
                raise ValueError(f"Record id {record_id} not found in the database.") 
            logger.info(f"Deleting record {record.id}")
            session.delete(record)
            session.commit()
            return {"message": f"Record {record.id} deleted successfully."}, True
        
        except Exception as e:
            return {"error": str(e)}, False


class TestEmrUtils(unittest.TestCase):
    def setUp(self):
        pass

    def test_create_record(self):
                # Create a record example
        record_data = {
            "type": RecordType.MEDICAL_RECORD,
            "table_name": SpeakCareEmr.WEIGHTS_TABLE,
            "patient_name": "John Doe",
            "nurse_name": "Sara Foster",
            "fields": {
                 "Units": "Lbs",
                 "Weight": 120,
                 "Scale": "Bath"
            }
        }
        response, record_id = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)
        self.assertEqual(response['message'], "EMR record created successfully")

        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.PENDING)
        logger.info(f"Created record {record_id}")

    def test_create_and_update_record(self):
                # Create a record example
        record_data = {
            "type": RecordType.MEDICAL_RECORD,
            "table_name": SpeakCareEmr.WEIGHTS_TABLE,
            "patient_name": "John Doe",
            "nurse_name": "Sara Foster",
            "fields": {
                 "Units": "Pounds", # use wrong field here
                 "Weight": 120,
                 "Scale": "Bath"
            }
        }
        response, record_id = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)        
        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.state, RecordState.ERRORS)
        logger.info(f"Record {record_id} created with errors:{record.errors}")

        # fix the record
        record_data = {
            "patient_name": "John Doe",
            "nurse_name": "Sara Foster",
            "fields": {
                 "Units": "Lbs",
                 "Scale": "Bath"
                 # not proviuind Weight intentionally to test the partial update
            }
        }
        response, record_id = EmrUtils.update_record(record_data, record_id)
        record, err = EmrUtils.get_record(record_id)
        self.assertEqual(record.id, record_id)
        # check that state is now PENDING
        self.assertEqual(record.state, RecordState.PENDING)
        logger.info(f"Created record {record_id}")


    def test_get_all_record_writable_schema(self):
        # Getting all table schema aexample
        table_names = EmrUtils.get_table_names()
        for table_name in table_names:
            logger.info(f'Getting schema for table {table_name}')
            record_schema, secitions_schema = EmrUtils.get_record_writable_schema(table_name)
            self.assertIsNotNone(record_schema)
            logger.debug(f'{table_name} Table schema: {json.dumps(record_schema, indent=4)}') 
            if secitions_schema:
                for section, schema in secitions_schema.items():
                    logger.info(f"Getting schema for section {section} in table {table_name}")
                    logger.debug(f"{table_name} Table {section} section schema: {json.dumps(schema, indent=4)}")
    



if __name__ == '__main__':
    unittest.main()
