from datetime import datetime
from speakcare_emr import SpeakCareEmr
import logging
from config import SpeakCareEmrApiconfig
from speakcare_emr import get_emr_api_instance
from models import MedicalRecords, Transcripts, RecordType, RecordState, TranscriptState, SpeakCareDB, init_speakcare_db
from sqlalchemy.orm import sessionmaker, Session
import sys
import json
from speakcare_logging import create_logger
from typing import Optional
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload
from sqlalchemy import select
import copy
import traceback
from airtable_schema import FieldTypes
logger = create_logger('speackcare.emr.utils')

class RecordStateError(Exception): ...

# Initialize the EMR API singleton early in the app setup
emr_api = get_emr_api_instance(SpeakCareEmrApiconfig)
if not emr_api:
    logger.error('Failed to initialize EMR API')
    raise Exception('Failed to initialize EMR API')

#db = get_speakcare_db_instance()

class EmrUtils:
    db : Optional[SpeakCareDB] = None
    @staticmethod
    def init_db(db_directory = None, create_db=False):
        EmrUtils.db = init_speakcare_db(db_directory, create_db=create_db)

    @staticmethod
    def cleanup_db(delete_db_files = False):
        if EmrUtils.db:
            EmrUtils.db.do_cleanup(delete_db_files)
            EmrUtils.db = None

    @staticmethod
    def get_patient_info(name):
        """
        get_patient_info
        """
        foundName, patientId, patientEmrId = emr_api.lookup_patient(name)

        if not patientEmrId:
            return None

        emr_patient = emr_api.get_patient_by_emr_id(patientEmrId)
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
        # Add the patient name field to the main schema - we need it for all main schemas
        main_schema['fields'].append({
            "name": "patient_name",
            "type": FieldTypes.SINGLE_LINE_TEXT.value,
            "description": "required"
        })

                # always require patient_name


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
    def validate_record(table_name: str, data: dict, errors: list = []):
        """
        validate_record_data
        """
        return emr_api.validate_record(tableName=table_name, record=data, errors=errors)
    
    @staticmethod
    def validate_partial_record(table_name: str, data: dict, errors: list = []):
        """
        validate_partial_record_data
        """
        return emr_api.validate_partial_record(tableName=table_name, record=data, errors=errors)

    @staticmethod
    def lookup_patient(name):
        """
        lookup_patient
        """
        return emr_api.lookup_patient(name)
    
    @staticmethod
    def __record_validation_helper(table_name: str,
                                   patient_name: str,
                                   nurse_name: str,
                                   fields: dict,
                                   sections = [],
                                   patient_id: str = None, 
                                   nurse_id: str = None):
        _errors =[]
        _state = RecordState.PENDING
        _patient_name = patient_name
        _patient_id = patient_id
        _nurse_name = nurse_name
        _nurse_id = nurse_id
        _valid_sections = []
        
         # validate patient
        foundPatientByName = None
        foundPatientIdByName = None
        foundPatientByPatientId = None
        foundPatientByName, foundPatientIdByName, patientEmrId = emr_api.lookup_patient(patient_name)

        if not foundPatientByName: # Patient name is mandatory and must be found
            _errors.append(f"Patient '{patient_name}' not found in the EMR.")
            _state = RecordState.ERRORS
        elif patient_id: # if patient id is provided, it MUST match the patient name
            foundPatientByPatientId, patientEmrId = emr_api.lookup_patient_by_id(patient_id)
            if not foundPatientByPatientId: # if not found it is an error
                _errors.append(f"Patient ID '{patient_id}' not found in the EMR.")
                _state = RecordState.ERRORS
            elif patient_id != foundPatientIdByName: # if found, the provided patient id must match the found patient id by name
                _errors.append(f"Patient ID '{patient_id}' does not match the patient ID '{foundPatientIdByName}' found by name '{patient_name}'.")
                _state = RecordState.ERRORS
            elif foundPatientByPatientId != foundPatientByName: # if found patient by id, it must match name found by name
                _errors.append(f"Patient name '{foundPatientByPatientId}' found by patient ID {patient_id} does not match the name '{foundPatientByName}' found by name '{patient_name}'.")
                _state = RecordState.ERRORS
            else: # all good
                _patient_name = foundPatientByPatientId
        else: # only patient name is provided
            _patient_name = foundPatientByName
            _patient_id = foundPatientIdByName


        # validate nurse
        foundNurseByName = None
        foundNurseIdByName = None
        foundNurseByNurseId = None
        foundNurseByName, foundNurseIdByName, nurseEmrId = emr_api.lookup_nurse(nurse_name)

        if not foundNurseByName: # Nurse name is mandatory and must be found
            _errors.append(f"Nurse '{nurse_name}' not found in the EMR.")
            _state = RecordState.ERRORS
        elif nurse_id: # if nurse id is provided, it MUST match the nurse name
            foundNurseByNurseId, nurseEmrId = emr_api.lookup_nurse_by_id(nurse_id)
            if not foundNurseByNurseId: # if not found it is an error
                _errors.append(f"Nurse ID '{nurse_id}' not found in the EMR.")
                _state = RecordState.ERRORS
            elif nurse_id != foundNurseIdByName: # if found, the provided nurse id must match the found nurse id by name
                _errors.append(f"Nurse ID '{nurse_id}' does not match the nurse ID '{foundNurseIdByName}' found by name '{nurse_name}'.")
                _state = RecordState.ERRORS
            elif foundNurseByNurseId != foundNurseByName: # if found nurse by id, it must match name found by name
                _errors.append(f"Nurse name '{foundNurseByNurseId}' found by nurse ID {nurse_id} does not match the name '{foundNurseByName}' found by name '{nurse_name}'.")
                _state = RecordState.ERRORS
            else: # all good
                _nurse_name = foundNurseByNurseId
        else: # only nurse name is provided
            _nurse_name = foundNurseByName
            _nurse_id = foundNurseIdByName

        # validate the record fields - we always valuadte the full record (not using parital validation) 
        # as we are validating the merge of existing record with the updated fields
        isValid, _valid_fields = EmrUtils.validate_record(table_name, fields, _errors)
        if not isValid:
            _state = RecordState.ERRORS

        if sections and table_name in SpeakCareEmr.TABLE_SECTIONS:  
            for section in sections:
                section_name = section.get('table_name', None)
                section_fields = section.get('fields', None)
                if not section_name in SpeakCareEmr.TABLE_SECTIONS[table_name]:
                    err = f"Section '{section_name}' not found in table '{table_name}'"
                    logger.error(err)
                    _errors.append(err)
                    _state = RecordState.ERRORS
                elif section_name and section_fields:
                    isValid, section_valid_fields =\
                            EmrUtils.validate_record(section_name, section_fields, _errors)
                    if isValid:
                        _valid_sections.append(
                            {
                                'section_name': section_name,
                                'fields': section_valid_fields
                            }
                        )
                    else:
                        _state = RecordState.ERRORS
        elif sections and not table_name in SpeakCareEmr.TABLE_SECTIONS:
                #create a list from sections field 'table_name'
                _sections_names = [section.get('table_name', None) for section in sections]
                err = f"Sections '{_sections_names}' provided for table '{table_name}' that has no sections"
                logger.error(err)
                _errors.append(err)
                _state = RecordState.ERRORS
            
        return _state, _errors, _patient_name, _patient_id, _nurse_name, _nurse_id, _valid_fields, _valid_sections


    @staticmethod
    def get_record(record_id: int, load_transcript: bool = False):
        """
        Get the emr record.
        """
        session = EmrUtils.db.SpeakCareDBSession()
        try:
            if load_transcript: #preload the transcript
                stmt = select(MedicalRecords).options(joinedload(MedicalRecords.transcript)).where(MedicalRecords.id == record_id)
                record = session.execute(stmt).scalar_one_or_none()
            else:
                record = session.get(MedicalRecords, record_id)
            
            if not record:
                raise KeyError(f"Record id {record_id} not found in the database.")
            else:
                return record, None
            
        except KeyError as e:
            logger.error(f"Error getting EMR record id {record_id}: {e}")
            session.rollback()
            return None, {"error": str(e)}
        finally:
            EmrUtils.db.SpeakCareDBSession.remove()
        
    @staticmethod
    def get_all_records(state: RecordState = None, table_name: str = None):
        """
        Get the emr records.
        """
        session = EmrUtils.db.SpeakCareDBSession()
        try:
            query = session.query(MedicalRecords)
            # records = session.query(MedicalRecords).all()
            if state:
                query = query.filter_by(state=state)
            if table_name:
                query = query.filter_by(table_name=table_name)
            
            records = query.all()
            return records, None
            
        except ValueError as e:
            err = f"Error getting all EMR records: {e}"
            logger.error(err)
            session.rollback()
            return None, {"error": err}
        finally:
            EmrUtils.db.SpeakCareDBSession.remove()



    @staticmethod
    def create_record(data: dict, transcript_id: int = None):
        """
        Creates a new EMR record linked to a given transcript.
        Returns a tuple: message and the new record id if the record is successfully created, 
        otherwise returns an error message and None.

        :param session: The SQLAlchemy session to use for the database operations.
        :param data: A dictionary containing the data for the medical record.
        :return: A tuple containing the a success or error message and an HTTP status code and the record id.
        """


        # Perform any additional validity checks on the data
        # Example: Check if the data dictionary contains necessary keys
        session = EmrUtils.db.SpeakCareDBSession()
        try:
            # first check for unrecoverable errors
            
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
            _sections = data.get('sections', [])
            _transcript = None


            # Check if the transcript_ids exists
            if transcript_id is not None:
                _transcript = session.get(Transcripts, transcript_id)
                #_transcript = session.query(Transcripts).get(transcript_id)
                if not _transcript:
                    raise ValueError(f"Transcript if {transcript_id} not found")
                
            _table_id = EmrUtils.get_table_id(_table_name)
            if not _table_id:
                raise ValueError(f"Table name {_table_name} not found in the EMR.")

                # fields data integrity check is done inside the create_record function - no need to do it here
            _state, _errors, _patient_name, _patient_id, _nurse_name, _nurse_id, _valid_fields, _valid_sections =\
                EmrUtils.__record_validation_helper(table_name= _table_name, patient_name= _patient_name, nurse_name=_nurse_name, 
                                                    fields=_fields, sections=_sections, patient_id=_patient_id, nurse_id=_nurse_id)

            new_record = MedicalRecords(
                type= _type,  # Convert to Enum
                table_name=_table_name,
                patient_name=_patient_name,
                patient_id= _patient_id,
                nurse_name=_nurse_name,
                nurse_id= _nurse_id,
                fields= _valid_fields,
                sections = _valid_sections,
                transcript = _transcript,
                state= _state,
                errors = _errors
            )

            if _transcript is not None:
                if _state == RecordState.ERRORS:
                    _transcript.state = TranscriptState.ERRORS
                else:
                    _transcript.state = TranscriptState.PROCESSED
            
            # Add and commit the new record to the database
            session.add(new_record)
            session.commit()
            if _state == RecordState.ERRORS:
                return new_record.id, _state, {"error": f"EMR record created with errors: {json.dumps(_errors)}", "id": new_record.id}
            else:
                return new_record.id, _state, {"message": "EMR record created successfully", "id": new_record.id}

        except ValueError as e:
            logger.error(f"Error creating EMR record: {e}")
            session.rollback()
            return None, RecordState.ERRORS, {"error": str(e)}
        
        finally:    
            EmrUtils.db.SpeakCareDBSession.remove()
            

    @staticmethod
    def update_record(updates: dict, record_id: int):
        """
        Returns a tuple: message and True if the record is successfully updated, 
        otherwise returns an error message and False.

        :param session: The SQLAlchemy session to use for the database operations.
        :param data: A dictionary containing the data for the updated record.
        :param record_id: The id of the record to update.
        :return: A tuple containing the a success or error message and an HTTP status code.
        """
        session = EmrUtils.db.SpeakCareDBSession()
        try:
            # first check for unrecoverable errors
            if not updates:
                err = "The updates dictionary is empty or None record id {record_id}."
                logger.error(err)
                raise ValueError(err)
            
            record: Optional[MedicalRecords] = session.get(MedicalRecords, record_id)
            if not record:
                err = f"Record id {record_id} not found in the database."
                logger.error(err)
                raise KeyError(err)
            
            if record.state in [RecordState.COMMITTED, RecordState.DISCARDED]:
                err = f"Record is {record_id} is in {record.state} state and cannot be updated."
                logger.error(err)
                raise RecordStateError(err)    
        
            # fields data integrity check is done inside the create_record function - no need to do it here
            # for now we allow update only if the result will not be in the ERROR state 
            # update is supposed to fix an error or update a pending record, not create new ones.
   
            # prepare the merge of the existing record with the updates
            _patient_name = updates.get('patient_name', record.patient_name)
            _patient_id =  updates.get('patient_id', record.patient_id)
            _nurse_name = updates.get('nurse_name', record.nurse_name)
            _nurse_id = updates.get('nurse_id', record.nurse_id)
            _fields = updates.get('fields', None)
            _sections = updates.get('sections', [])
            if _fields:
                old_fields = copy.deepcopy(record.fields)
                old_fields.update(_fields)
                _fields = old_fields
            else:
                _fields = record.fields

            # first validate the record with the new fields

            _new_state, _errors, _patient_name, _patient_id, _nurse_name, _nurse_id, _valid_fields, _valid_sections =\
                EmrUtils.__record_validation_helper(table_name=record.table_name, patient_name=_patient_name, nurse_name=_nurse_name, 
                                                    fields=_fields, sections=_sections,  patient_id=_patient_id, nurse_id=_nurse_id)
            
            if _new_state == RecordState.ERRORS:
                err_message = f"Record {record_id} cannot be updated with {updates} as it will result in errors: {_errors}"
                logger.error(err_message)
                raise RecordStateError(err_message) 
            
            # if we are here, we can safely update the record
            elif _new_state == RecordState.PENDING:
                # we can safely update the record
                record.patient_name = _patient_name
                record.patient_id = _patient_id
                record.nurse_name = _nurse_name
                record.nurse_id = _nurse_id
                record.fields = _valid_fields
                record.sections = _valid_sections
                record.state = _new_state
                record.errors = _errors
                flag_modified(record, 'fields')
                flag_modified(record, 'sections')
                flag_modified(record, 'errors')
            
                # Commit the udpated record to the database
                session.commit()
                return True, {"message": "EMR record updated successfully", "id": record_id}

        except (ValueError, KeyError, RecordStateError) as e:
            session.rollback()
            logger.error(f"Error updating EMR record: {e}")
            return False, {"error": str(e)}
        finally:
            EmrUtils.db.SpeakCareDBSession.remove()
        

    @staticmethod
    def discard_record(record_id: int):
        """
        Returns a tuple: message and the record id if the record is successfully discarded, 
        otherwise returns ane error message and None.
        """
        # Logic to discard the record
        session = EmrUtils.db.SpeakCareDBSession()
        try:
            record: Optional[MedicalRecords] = session.get(MedicalRecords, record_id)
            if not record:
                raise KeyError(f"Record id {record_id} not found in the database.")
            elif record.state == RecordState.COMMITTED:  
                raise RecordStateError(f"Record id {record.id} cannot be discarded as it already COMMITTED.")

            logger.info(f"Discarding record {record.id}")
            record.state = RecordState.DISCARDED
            session.commit()
            return True, {"message": f"Record {record.id} discarded successfully."}
        
        except Exception as e:
            session.rollback()
            return False, {"error": str(e)}
        finally:
            EmrUtils.db.SpeakCareDBSession.remove()
    
    @staticmethod
    def delete_record(record_id: int):
        """
        Returns a message and True if the record is successfully deleted, 
        otherwise returns error message and False.
        """
        session = EmrUtils.db.SpeakCareDBSession()
        try:
            record: Optional[MedicalRecords] = session.get(MedicalRecords, record_id)
            if not record:
                raise KeyError(f"Record id {record_id} not found in the database.") 
            logger.info(f"Deleting record {record.id}")
            session.delete(record)
            session.commit()
            return True, {"message": f"Record {record.id} deleted successfully."}
        
        except Exception as e:
            session.rollback()
            return False, {"error": str(e)}
        finally:
            EmrUtils.db.SpeakCareDBSession.remove()

    ### EMR interaction methods ###


    @staticmethod
    def commit_record_to_emr(record_id: int):
        """
        Returns a tuple: The record EMR id if the record is successfully committed to the EMR, the record state, and a message 
        otherwise returns ane error message and None.
        """
        session = EmrUtils.db.SpeakCareDBSession()
        # prepare to commit the record to the EMR
        try:
            # first verify that the record is a PENDING state
            record: Optional[MedicalRecords] = session.get(MedicalRecords, record_id)
            if not record:
                raise KeyError(f"Record id {record_id} not found in the database.")
            elif record.state != RecordState.PENDING:  # Example check to ensure the record is in a valid state to be committed
                raise RecordStateError(f"Record id {record.id} cannot be commited as it is in '{record.state}' state.")
            
            # from here record should be ready for commit with no errors
            foundPatient, foundPatientId, patientEmrId = emr_api.lookup_patient(record.patient_name) 
            if not foundPatient:
                record.errors
                raise ValueError(f"Patient {record.patient_name} not found in the EMR.")
            
            
            foundNurse, foundNurseId, nurseEmrId = emr_api.lookup_nurse(record.nurse_name)
            if not foundNurse:
                raise ValueError(f"Nurse {record.nurse_name} not found in the EMR.")
            # update the nurse name to the correct one as matched in the database
            
            table_name  = record.table_name
            record_fields = record.fields
            # TODO - continue from here
            record_type = record.type
            errors = record.errors
            if (record_type == RecordType.MEDICAL_RECORD):
                emr_record, url, err = emr_api.create_medical_record(tableName=record.table_name, record=record_fields, 
                                                                     patientEmrId=patientEmrId, createdByNurseEmrId=nurseEmrId,
                                                                     errors=errors)
                if not emr_record:    
                    raise ValueError(f"Failed to create medical record {record_fields} in table {table_name}. Error: {err}")            
                else:
                    # update the record with the EMR record ID and URL
                    record.emr_record_id = emr_record['id']
                    record.emr_url = url                
            elif record_type == RecordType.ASSESSMENT:
                emr_record, url, err = emr_api.create_assessment(assessmentTableName=record.table_name, record=record_fields, 
                                                                 patientEmrId=patientEmrId, createdByNurseEmrId=nurseEmrId,
                                                                 errors=errors)
                if not emr_record:
                    raise ValueError(f"Failed to create assessment record {record_fields} in table {table_name}. Error: {err}")
                
                record.emr_record_id = emr_record['id']
                record.emr_url = url
                if record.sections:
                    for section in record.sections:
                        section_name = section.get('section_name', None)
                        section_fields = section.get('fields', None)
                        if section_name and section_fields:
                            emr_record, url, err = emr_api.create_assessment_section(sectionTableName=section_name, record=section_fields, 
                                                                                     patientEmrId=patientEmrId, assessmentId=record.emr_record_id, 
                                                                                     createdByNurseEmrId=nurseEmrId, errors=errors)
                            if not emr_record:
                                raise ValueError(f"Failed to create assessment section '{section_name} fields: '{section_fields}' in assessment {table_name}. Error: {err}")
            else:
                raise ValueError(f"Record type {record_type} not supported.")            

            # update the record state to 'COMMITTED'
            logger.info(f"Commiting record {record.id}")
            record.state = RecordState.COMMITTED
            flag_modified(record, 'errors')
            session.commit()
            return record.emr_record_id, record.state, {"message": f"Record {record.id} commited successfully to the EMR."}
        
        except RecordStateError as e:
            # in case of record state error, we don't want to update the record state
            logger.error(e)
            session.rollback()
            return None, None, {"error": str(e)}
        except (KeyError, ValueError) as e:
        # Handle the error by adding it to the record's errors field
            errors = record.errors.get('errors', []) if record.errors else []  # Get existing errors, defaulting to an empty list
            if not isinstance(errors, list):        # Ensure it's a list
                errors = []
            errors.append(str(e))                   # Add the new error message
            record.errors = {"errors": errors}      # Update the record's errors field with the modified list
            flag_modified(record, 'errors')         # Flag the 'errors' field as modified
            record.state = RecordState.ERRORS       # Update the record's state to 'ERRORS'
            session.commit()                        # Commit the changes to the database
            logger.error(f"Error committing record {record.id} to the EMR: {e}")
            return None, record.state, {"error": str(e)}          # Return error response and status code
        finally:
            EmrUtils.db.SpeakCareDBSession.remove()
        

    @staticmethod
    def sign_assessgment(record_id: id):
        session = EmrUtils.db.SpeakCareDBSession()
        record = None
        # prepare to commit the record to the EMR
        try:
            # first verify that the record is a PENDING state
            record: Optional[MedicalRecords] = session.get(MedicalRecords, record_id)
            if not record:
                raise KeyError(f"Record id {record_id} not found in the database.")
            elif record.state in [RecordState.ERRORS, RecordState.DISCARDED]:  # Example check to ensure the record is in a valid state to be committed
                raise RecordStateError(f"Record id {record.id} cannot be commited as it is in '{record.state}' state.")
            elif record.type != RecordType.ASSESSMENT:
                raise TypeError(f"Sign assessment - record type '{record.type}' is not ASSESSMENT.")
            
            foundNurse, foundNurseId, nurseEmrId = emr_api.lookup_nurse(record.nurse_name)
            if not foundNurse:
                raise ValueError(f"Nurse {record.nurse_name} not found in the EMR.")
            # update the nurse name to the correct one as matched in the database
            
            table_name  = record.table_name
            assessment_id = record.emr_record_id
            emr_record, err = emr_api.sign_assessment(assessmentTableName=table_name, assessmentId=assessment_id, signedByNurseEmrId=nurseEmrId)
            if not emr_record:
                raise ValueError(f"Failed to sign assessment record {record.fields} in table {table_name}. Error: {err}")
        except Exception as e:
            err = f"Failed to sign assessment {record_id}. Error {e}"
            if record:
                record.errors.append(err)
                # register the errors
                session.commit()
            logger.error(err)

        finally:
            EmrUtils.db.SpeakCareDBSession.remove()


    @staticmethod
    def get_emr_record(record_id: int):
        """
        Returns the EMR record for the given record id.
        """
        session = EmrUtils.db.SpeakCareDBSession()
        try:
            record: Optional[MedicalRecords] = session.get(MedicalRecords, record_id)
            if not record:
                raise KeyError(f"Record id {record_id} not found in the database.")
            elif record.state != RecordState.COMMITTED:
                raise ValueError(f"Record id {record.id} is not in '{RecordState.COMMITTED}' state.")
            emr_record = emr_api.get_record(tableId= record.table_name, recordId= record.emr_record_id)
            if not emr_record:
                raise ValueError(f"EMR record id {record.emr_record_id} not found in table {record.table_name} the EMR.")
            
            return  emr_record, {"message": f"EMR record {record.emr_record_id} retreived from table {record.table_name} ."}
        
        except (KeyError, ValueError) as e:
            session.rollback()
            logger.error(f"Error getting EMR record id {record_id}: {e}")
            return None, {"error": str(e)}
        finally: 
            EmrUtils.db.SpeakCareDBSession.remove()
    
    @staticmethod
    def get_emr_record_by_emr_record_id(tableId, emr_record_id: int):
        """
        Returns the EMR record for the given record id.
        """
        emr_record = emr_api.get_record(tableId= tableId, recordId= emr_record_id)
        if not emr_record:
            return None, {"error": f"EMR record id {emr_record_id} not found in table {tableId} the EMR."}
        else:
            return emr_record, {"message": f"EMR record {emr_record_id} retreived from table {tableId} ."}
        

    ### Transcript DB methods ###

    @staticmethod
    def add_transcript(transcript: str):
        """
        Create a new transcript in the database and return its id.
        Return the new transcript id, or None if it fails.
        """
        session = EmrUtils.db.SpeakCareDBSession()
        try:
            new_transcript = Transcripts(text=transcript)
            if not new_transcript:
                err = "Failed to create new transcript."
                logger.error(err)
                raise ValueError(err)
            
            session.add(new_transcript)
            session.commit()
            return new_transcript.id, {"message": "Transcript created successfully", "id": new_transcript.id}
        except SQLAlchemyError as e:
            # Log the SQLAlchemy error
            logger.error(f"SQLAlchemyError: Failed to add transcript: {e}")
            # Rollback the session in case of an SQLAlchemy error
            session.rollback()
            return None, {"error": str(e)}        
        except Exception as e:
            session.rollback()
            logger.error(f"Error creating transcript: {e}")
            return None, {"error": str(e)}
        finally:
            EmrUtils.db.SpeakCareDBSession.remove()

    @staticmethod
    def get_all_transcripts(text_limit: int = 200, state: TranscriptState = None):
        """
        Return a dictionary with all transcripts but truncate the text to first text_limit characters.
        If state is given (not None), query the database only for these transcripts that are in that state.
        """
        session = EmrUtils.db.SpeakCareDBSession()
        try:
            query = session.query(Transcripts)
            if state:
                query = query.filter_by(state=state)
            transcripts = query.all()
            result = []
            for transcript in transcripts:
                truncated_text = transcript.text[:text_limit]
                result.append({
                    'id': transcript.id,
                    'text': truncated_text,
                    'state': transcript.state,
                    'errors': transcript.errors,
                    'created_time': transcript.created_time,
                    'modified_time': transcript.modified_time
                })
            return result, {"message": "Transcripts retrieved successfully."}
        except SQLAlchemyError as e:
            # Log the SQLAlchemy error
            logger.error(f"SQLAlchemyError: Failed to add transcript: {e}")
            # Rollback the session in case of an SQLAlchemy error
            session.rollback()
            return None, {"error": str(e)}        
        except Exception as e:
            session.rollback()
            logger.error(f"Error retrieving transcripts: {e}")
            return None, {"error": str(e)}
        finally:
            EmrUtils.db.SpeakCareDBSession.remove()
    
    @staticmethod
    def get_transcript(transcript_id: int, load_medical_records: bool = False):
        """
        Get the transcript record by transcript_id and return the transcript record, or None if failed.
        """
        session = EmrUtils.db.SpeakCareDBSession()
        try:
            if load_medical_records:
                stmt = select(Transcripts).options(joinedload(Transcripts.medical_records)).where(Transcripts.id == transcript_id)
                result = session.execute(stmt).unique()
                transcript = result.scalar_one_or_none()
            else:
                transcript = session.get(Transcripts, transcript_id)
            if not transcript:
                err = f"Transcript with ID {transcript_id} not found."
                logger.error(err)
                raise KeyError(err)
            
            return transcript, {"message": f"Transcript id {transcript_id} retrieved successfully."}
        except Exception as e:
            session.rollback()
            logger.error(f"Error retrieving transcript: {e}")
            return None, {"error": str(e)}
        finally:
            EmrUtils.db.SpeakCareDBSession.remove()

    @staticmethod
    def update_transcript_state(transcript_id: int, state: TranscriptState):
        """
        Get the transcript record by transcript_id and update the state.
        Return True for success or False for failure.
        """
        if transcript_id is None or state is None:
            err = "Transcript ID and state are required."
            logger.error(err)
            return False, {"error": err}
        
        session = EmrUtils.db.SpeakCareDBSession()
        try:
            transcript = session.get(Transcripts, transcript_id)
            if transcript:
                transcript.state = state
                session.commit()
                return True, {"message": f"Transcript state updated to {state}."}
            else:
                err = f"Transcript with ID {transcript_id} not found."
                logger.error(err)
                raise KeyError(err)
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating transcript state: {e}")
            return False, {"error": str(e)}
        finally:
            EmrUtils.db.SpeakCareDBSession.remove()

    @staticmethod
    def delete_transcript(transcript_id: int):
        """
        Delete the transcript by transcript_id.
        """
        session = EmrUtils.db.SpeakCareDBSession()
        try:
            transcript = session.get(Transcripts, transcript_id)
            if transcript:
                session.delete(transcript)
                session.commit()
                return True, {"message": f"Transcript with ID {transcript_id} deleted successfully."}
            else:
                err = f"Transcript with ID {transcript_id} not found."
                logger.error(err)
                raise KeyError(err)
        except Exception as e:
            logger.error(f"Error deleting transcript: {e}")
            session.rollback()
            return False, {"error": str(e)}
        finally:
            EmrUtils.db.SpeakCareDBSession.remove()