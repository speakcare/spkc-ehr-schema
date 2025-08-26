import os, sys

from dotenv.main import logger
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pyairtable import Api as AirtableApi
import json
import logging
import requests
import time
from name_matching import NameMatcher
from speakcare_schema import AirtableSchema
import copy
from typing import Dict
from speakcare_emr_tables import SpeakCareEmrTables
from backend.speakcare_env import SpeakcareEnv
from backend.speakcare_airtable_api import SpeakCareAirtableApi
from config import SpeakCareEmrApiconfig

# Load the .env file
SpeakcareEnv.load_env()
AIRTABLE_APP_BASE_ID = os.getenv('AIRTABLE_APP_BASE_ID')
AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')

class SpeakCareEmr(SpeakCareEmrTables):


    INTERNAL_FIELDS = ['Patient', 'CreatedBy', 'Doctor', 'SpeakCare']
    READONLY_FIELD_TYPES = ['autoNumber', 'barcode', 'button', 'collaborator', 'count', 'createdBy',  'createdTime', 
                            'formula', 'lastModifiedTime', 'lastModifiedBy', 'multipleCollaborators', 'multipleLookupValues',
                            'multipleRecordLinks', 'rollup', 'singleCollaborator', 'multipleAttachments']

    def __init__(self, config, logger: logging.Logger):
        self.logger = logger
        self.tables = None
        self.api = SpeakCareAirtableApi(config, logger=logger)
        self.nameMatcher = NameMatcher(primary_threshold=90, secondary_threshold=75)
        self.initialze()

    def initialze(self):
        self.load_tables()
        self.load_patients()
        self.load_nurses()
    
    def __writable_fields(self, tableSchema):
        fields = []
        primaryFieldId = tableSchema['primaryFieldId']
        for field in tableSchema['fields']:
            if field['name'] not in self.INTERNAL_FIELDS and\
               field['type'] not in self.READONLY_FIELD_TYPES and\
               (self.is_test_env() == True or field['id'] != primaryFieldId):
                     _field = copy.deepcopy(field)
                     fields.append(_field)
        
        return fields

    def create_table(self, table:dict):
        return self.api.create_table(table)

    def get_raw_table_schema(self, tableName: str):
        tables = self.api.retreive_all_tables_schema()
        for table in tables:
            if table['name'] == tableName:
                return table
        return None

    def load_tables(self):
        if not self.tables:
            tables = self.api.retreive_all_tables_schema()
            self.tables = {}
            self.tableEmrSchemas: Dict[str, AirtableSchema] = {}
            # Traverse the tables and create writable schema
            for table in tables:
                # add the table to the tables dictionary
                tableName = table['name']
                self.tables[tableName] = table
                # Check if the table is in not in READONLY_TABLES
                
                is_person_table = tableName in self.PERSON_TABLES()
                # if tableName not in self.READONLY_TABLES:
                # Create writeable schema by copy from table
                writeableSchema = copy.deepcopy(table)
                # replace the fields with the writable fields
                writeableSchema['fields'] = self.__writable_fields(table)
                # create the EmrTableSchema object
                is_person_table = tableName in self.PERSON_TABLES()
                emrSchema = AirtableSchema(table_name=tableName, table_schema=writeableSchema, is_person_table=is_person_table)
                # add the EmrTableSchema to the tableWriteableSchemas dictionary
                self.logger.debug(f'Created writable schema for table {tableName}')
                self.tableEmrSchemas[tableName] = emrSchema
            
            # register sections
            for tableName, sections in self.TABLE_SECTIONS().items():
                if tableName in self.tableEmrSchemas:
                    tableSchema = self.tableEmrSchemas.get(tableName)
                    for section in sections:
                        if section in self.tableEmrSchemas:
                            sectionSchema = self.tableEmrSchemas.get(section)
                            if sectionSchema:
                                tableSchema.add_section(section, sectionSchema, required=True)
                                self.logger.debug(f'Added section {section} to table {tableName}')
                            else:
                                self.logger.error(f'Failed to add section {section} to table {tableName}')
        
        self.logger.debug(f'Loaded tables. Tables')
        return self.tables
    
    def get_emr_table_names(self):
        return get_emr_api_instance(SpeakCareEmrApiconfig).EMR_TABLES()
   
    def get_emr_table_section_names(self, tableName=None):
        if not tableName:
            return None
        return SpeakCareEmr.TABLE_SECTIONS().get(tableName)

    def get_table_id(self, tableName):
        table = self.tables.get(tableName)
        if table:
            return table['id']
        else:
            return None
            
    def get_table_name(self, tableId):
        for table in self.tables:
            if table['id'] == tableId:
                return table['name']
        return None

    def get_airtable_schema(self, tableId=None, tableName=None):
        if tableName:
            return self.tables.get(tableName)
        elif tableId:
            for table in self.tables:
                if table['id'] == tableId:
                    return table
        else:
            return None
        
    
    def get_table_json_schema(self, tableId=None, tableName=None):
        if not tableId and not tableName:
            self.logger.warning(f'get_table_writable_schema: tableId and tableName are None')
            return None
        
        if tableId and not tableName:
            tableName = self.get_table_name(tableId)
            if not tableName:
                self.logger.warning(f'get_table_writable_schema: Table {tableId} not found')
                return None

        # if tableName in self.READONLY_TABLES:
        #     self.logger.warning(f'get_table_writable_schema: Table {tableName} is readonly')
        #     return None
        
        tableSchema = self.tableEmrSchemas.get(tableName)

        if not tableSchema:
            self.logger.error(f'get_table_writable_schema: Table {tableName} failed to get schema')
            return None

        if tableSchema.get_name() != tableName:
            error_message = f'get_table_writable_schema: Table {tableSchema.get_name()} is different from {tableName}'
            self.logger.error(error_message)
            raise ValueError(error_message)
        
        return tableSchema.get_json_schema()


    def is_table_multi_section(self, tableName):
        return tableName in self.TABLE_SECTIONS()

    def create_record(self, tableId, record):
        self.logger.debug(f'Creating record in table {tableId} with record {record}')
        record, url = self.api.create_record(tableId, record)
        return record, url
        
    def get_record(self, tableId, recordId):
        return self.api.get_record(tableId, recordId)
    
    def update_record(self, tableId, recordId, record):
        self.logger.debug(f'Update record in table {tableId} with record id {recordId} and record {record}')
        return self.api.update_record(tableId, recordId, record=record)
    
    def validate_record(self, tableName, record, errors):
        tableSchema = self.tableEmrSchemas.get(tableName)
        valid_fields = {}
        if not tableSchema:
            error = f'validate_record: Failed to get EMR schema for table {tableName}'
            self.logger.error(error)
            errors.append(error)
            return False, {}
        
        isValidRecord, valid_fields = tableSchema.validate_record(record=record, errors= errors)
        if not isValidRecord:
            err= f'validate_record: Invalid record {record} for table {tableName}.'
            self.logger.warning(err)
            errors.append(f'validate_record: Invalid record {record} for table {tableName}.')
            return False, valid_fields
        
        return True, valid_fields
    
    def validate_partial_record(self, tableName, record, errors):
        tableSchema = self.tableEmrSchemas.get(tableName)
        valid_fields = {}
        if not tableSchema:
            errors.append(f'validate_partial_record: Failed to get writable schema for table {tableName}')
            return False, {}
        
        isValidRecord, valid_fields = tableSchema.validate_partial_record(record=record, errors=errors)
        if not isValidRecord:
            errors.append(f'validate_partial_record: Invalid record {record} for table {tableName}.')
            return False, valid_fields
        
        return True, valid_fields
        
    def get_table_url(self, tableId=None, tableName=None):
        if tableId:
             _tableId = tableId
        elif tableName:
            _tableId = self.get_table_id(tableName)
        else:
            return None
        
        return f'{self.webBaseUrl}{_tableId}'
    
    def get_record_url(self, recordId, tableId=None, tableName=None):
        if tableId:
             _tableId = tableId
        elif tableName:
            _tableId = self.get_table_id(tableName)
        else:
            return None
        return f'{self.webBaseUrl}{_tableId}/{recordId}'
        

    def create_simple_record(self, tableName, record, 
                              patientEmrId, createdByNurseEmrId, errors=[]):
 
        
        isValidRecord, valid_fields = self.validate_record(tableName= tableName, record= record, errors=errors)
        if not isValidRecord:
            err_msg = f'create_medical_record: Invalid record {record} for table {tableName}.'
            errors.append(err_msg)
            self.logger.error(err_msg)
            return None, None, err_msg
        record['Patient'] = [patientEmrId]
        record['CreatedBy'] = [createdByNurseEmrId]
        record['SpeakCare'] = 'Draft'
        tableId = self.get_table_id(tableName)
        record, url = self.create_record(tableId= tableId, record=record)
        return record, url, None


    def create_multi_section_record(self, tableName, record, patientEmrId, createdByNurseEmrId, errors=[]):
        """
        Complex record has sections that are implemtedd in different tables
        """
        isValidRecord, valid_fields = self.validate_record(tableName=tableName, record=record, errors=errors)
        if not isValidRecord:
            err_msg = f'create_complex_record: Invalid record {record} for table {tableName}.'
            errors.append(err_msg)
            self.logger.error(err_msg)
            return None, None, err_msg        
                
        record['Patient'] = [patientEmrId]
        record['CreatedBy'] = [createdByNurseEmrId]
        record['SpeakCare'] = 'Draft'
        status = record.get('Status')
        if not status:
            record['Status'] = 'In progress'
    
        self.logger.debug(f'Creating assessment in table {tableName} with record {record}')
        record, url = self.create_record(tableName, record)
        return record, url, None
    
    def create_record_section(self, sectionTableName, record, patientEmrId,
                                  assessmentId, createdByNurseEmrId, errors=[]):
        
        isValidRecord, valid_fields = self.validate_record(tableName=sectionTableName, record=record, errors=errors)
        if not isValidRecord:
            err_msg = f'create_assessment_section: Invalid record {record} for table {sectionTableName}.'
            errors.append(err_msg)
            self.logger.error(err_msg)
            return None, None, err_msg         

        record['Patient'] = [patientEmrId]
        if not self.is_test_env():
            record['ParentRecord'] = [assessmentId]
        record['CreatedBy'] = [createdByNurseEmrId]
        self.logger.debug(f'Creating assessment section in table {sectionTableName} with record {record}')
        record, url = self.create_record(sectionTableName, record)
        return record, url, None
    
    def sign_assessment(self, assessmentTableName, assessmentId, signedByNurseEmrId):
        assessment = self.api.get_record(assessmentTableName, assessmentId)
        if assessment:
            record = {}
            record['Status'] = 'Completed'
            record['SignedBy'] = ','.join(signedByNurseEmrId) if isinstance(signedByNurseEmrId, list) else signedByNurseEmrId
            self.logger.debug(f'Sign assessment section in table {assessmentTableName} with record {record}')
            record = self.update_record(assessmentTableName, assessmentId, record)
            return record, None
        else:
            err_msg = f'sign_assessment: Failed to get assessment record with id {assessmentId}'
            self.logger.error(err_msg)
            return None, err_msg

    def get_record_id(self, record, expected_id_field_name):
        if self.is_test_env():
            return record['id']
        else:
            return record['fields'][expected_id_field_name]
        
# Patients methods
    def load_patients(self):
        self.api.load_table(self.PATIENTS_TABLE())
        self.patientNames=[]
        self.patientEmrIds=[]
        self.patientIds=[]
        patients = self.api.get_table_records(self.PATIENTS_TABLE())
        for patient in patients:
            self.patientNames.append(patient['fields']['FullName'])
            self.patientEmrIds.append(patient['id'])
            self.patientIds.append(self.get_record_id(patient, 'PatientID'))
        self.logger.debug(f'Loaded patients. Patients names: {self.patientNames}')

    def get_patients(self):
        return self.api.get_table_records(self.PATIENTS_TABLE())

    def get_patient_by_emr_id(self, patient_emr_id):
        return self.api.get_record(self.PATIENTS_TABLE(), patient_emr_id)
    
    def get_patient_by_id(self, patient_id):
        for index, patienId in enumerate(self.patientIds): 
            if patient_id == patienId:
                patientEmdId = self.patientEmrIds[index]
                return self.api.get_record(self.PATIENTS_TABLE(), patientEmdId)

    def __match_patient(self, patientName):
        matchedName, matchedIndex, score = self.nameMatcher.get_best_match(input_name= patientName, names_to_match= self.patientNames)
        if matchedName:
            return matchedName, self.patientIds[matchedIndex], self.patientEmrIds[matchedIndex]
        else:
            return None, None, None
    
    def match_patient(self, patientFullName):
        self.logger.debug(f"match_patient: {patientFullName}")
        matchedName, patientId, patientEmrId = self.__match_patient(patientFullName)
        if not matchedName:
            self.logger.info(f'Patient {patientFullName} not found')
        return matchedName, patientId, patientEmrId
    
    def lookup_patient_by_id(self, patient_id):
        for index, patienId in enumerate(self.patientIds): 
            if patient_id == patienId:
                return self.patientNames[index], self.patientEmrIds[index]
        return None, None

    def add_patient(self, patient):
        patient_name = patient.get('FullName')
        if patient_name in self.patientNames:
            patientId = self.patientIds[self.patientNames.index(patient_name)]
            self.logger.warning(f"Patient '{patient_name}' already exists with id {patientId}")
            return None
        patient_record, _ = self.api.create_record(self.PATIENTS_TABLE(), patient)
        if not patient_record:
            self.logger.error(f'Failed to create patient {patient}')
            return None
        else:
            self.patientNames.append(patient_record['fields']['FullName'])
            self.patientEmrIds.append(patient_record['id'])
            self.patientIds.append(self.get_record_id(patient_record, 'PatientID'))
            self.logger.info(f"Created patient '{patient_name}' with id PatientID '{self.get_record_id(patient_record, 'PatientID')}")
            return patient_record

    def update_patient(self, patientEmrId, patient):
        self.logger.debug(f'Updating patient {patientEmrId} with {patient}')
        return self.api.update_record(self.PATIENTS_TABLE(), patientEmrId, patient)

    def delete_patient(self, patientEmrId):
        try:
            idx = self.patientEmrIds.index(patientEmrId)
            recDeleted = self.api.delete_record(self.PATIENTS_TABLE(), patientEmrId)
            self.patientIds.pop(idx)
            self.patientEmrIds.pop(idx)
            self.patientNames.pop(idx)
            return recDeleted
        except Exception as e:
            self.logger.error(f'Failed to delete patient {patientEmrId} with error {e}')
            return None

# Nurses methods 
    def load_nurses(self):
        self.api.load_table(self.NURSES_TABLE())
        self.nurseNames = []
        self.nurseEmrIds = []
        self.nurseIds = []
        nurses = self.api.get_table_records(self.NURSES_TABLE())
        for nurse in nurses:
            self.nurseNames.append(nurse['fields']['Name'])
            self.nurseEmrIds.append(nurse['id'])
            self.nurseIds.append(self.get_record_id(nurse, 'NurseID'))
        self.logger.debug(f'Loaded nurses. Nurses names: {self.nurseNames}')

    def get_nurses(self):
        return self.api.get_table_records(self.NURSES_TABLE())
    
    def get_nurse_by_emr_id(self, nurse_emr_id):
        return self.api.get_record(self.NURSES_TABLE(), nurse_emr_id)
    
    def get_nurse_by_id(self, nurse_id):
        for index, nurseId in enumerate(self.nurseIds): 
            if nurse_id == nurseId:
                nurseEmrId = self.nurseEmrIds[index]
                return self.api.get_record(self.NURSES_TABLE(), nurseEmrId)
    
    def __match_nurse(self, nurseName):
        matchedName, matchedIndex, score = self.nameMatcher.get_best_match(input_name=  nurseName, names_to_match=  self.nurseNames)
        if matchedName:
            return matchedName, self.nurseIds[matchedIndex], self.nurseEmrIds[matchedIndex]
        else:
            return None, None, None
        
    def match_nurse(self, nurseName):
        matchedName, nurseId, nurseEmrId = self.__match_nurse(nurseName)
        if not matchedName:
            self.logger.info(f'Nurse {nurseName} not found')
        return matchedName, nurseId, nurseEmrId
    
    def lookup_nurse_by_id(self, nurse_id):
        for index, nurseId in enumerate(self.nurseIds): 
            if nurse_id == nurseId:
                return self.nurseNames[index], self.nurseEmrIds[index]
        return None, None
    
    def get_nurses_table_json_schema(self):
        return self.get_table_json_schema(tableName=self.NURSES_TABLE())

    def add_nurse(self, nurse):
        nurse_name = nurse.get('Name')
        if nurse_name in self.nurseNames:
            nurseId = self.nurseIds[self.nurseNames.index(nurse_name)]
            self.logger.warning(f"Nurse '{nurse_name}' already exists with id {nurseId}")
            return None
        nurse_record, _ = self.api.create_record(self.NURSES_TABLE(), nurse)
        if not nurse_record:
            self.logger.error(f'Failed to create nurse {nurse}')
            return None
        else:
            self.nurseNames.append(nurse_record['fields']['Name'])
            self.nurseEmrIds.append(nurse_record['id'])
            self.nurseIds.append(self.get_record_id(nurse_record, 'NurseID'))
            self.logger.info(f"Created nurse '{nurse_name}' with id NurseID '{self.get_record_id(nurse_record, 'NurseID')}")
            return nurse_record
    
    def update_nurse(self, nurseEmrId, nurse):
        self.logger.debug(f'Updating nurse {nurseEmrId} with {nurse}')
        return self.api.update_record(self.NURSES_TABLE(), nurseEmrId, nurse)
    
    def delete_nurse(self, nurseEmrId):
        try:
            idx = self.nurseEmrIds.index(nurseEmrId)
            recDeleted = self.api.delete_record(self.NURSES_TABLE(), nurseEmrId)
            self.nurseIds.pop(idx)
            self.nurseEmrIds.pop(idx)
            self.nurseNames.pop(idx)
            return recDeleted
        except Exception as e:
            self.logger.error(f'Failed to delete nurse {nurseEmrId} with error {e}')
            return None
    
    
    def get_nurse_patients(self, nurse_id):
        return self.api.get_record(self.NURSES_TABLE())['fields']['Patients']
    

__singletonInstance = None
def get_emr_api_instance(config=None):
    """
    Provides access to the singleton instance of EMRAPI.
    Initializes the instance if it hasn't been created yet.
    :param config: Optional configuration dictionary for initializing the instance.
    :return: Singleton instance of EMRAPI.
    """
    global __singletonInstance
    if __singletonInstance is None:
        if config is None:
            raise ValueError("Configuration is required for the initial creation of the SpeakCareEmrApi instance.")
        else:
            logger = config.get('logger')
            __singletonInstance = SpeakCareEmr(config, logger=logger)
    return __singletonInstance