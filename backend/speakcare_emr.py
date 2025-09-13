import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pyairtable import Api as AirtableApi
import logging
import requests
import time
from speakcare_common import NameMatcher
from speakcare_schema import AirtableSchema
import copy
from typing import Dict
from speakcare_emr_tables import SpeakCareEmrTables
from backend.speakcare_env import SpeakcareEnv

# Load the .env file
SpeakcareEnv.load_env()
AIRTABLE_APP_BASE_ID = os.getenv('AIRTABLE_APP_BASE_ID')
AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')

class SpeakCareEmr(SpeakCareEmrTables):


    METADATA_BASE_URL = 'https://api.airtable.com/v0/meta/bases'
    API_BASE_URL = 'https://api.airtable.com/v0'
    WEB_APP_BASE_URL = 'https://airtable.com'

    INTERNAL_FIELDS = ['Patient', 'CreatedBy', 'Doctor', 'SpeakCare']
    READONLY_FIELD_TYPES = ['autoNumber', 'barcode', 'button', 'collaborator', 'count', 'createdBy',  'createdTime', 
                            'formula', 'lastModifiedTime', 'lastModifiedBy', 'multipleCollaborators', 'multipleLookupValues',
                            'multipleRecordLinks', 'rollup', 'singleCollaborator', 'multipleAttachments']

    def __init__(self, baseId: str, logger: logging.Logger):
        self.apiKey = AIRTABLE_API_KEY
        self.api = AirtableApi(self.apiKey)
        self.appBaseId = baseId
        self.logger = logger
        self.tablesSchemaUrl = f'{self.METADATA_BASE_URL}/{baseId}/tables'
        self.apiBaseUrl = f'{self.API_BASE_URL}/{baseId}/'
        self.webBaseUrl = f'{self.WEB_APP_BASE_URL}/{baseId}/'
        self.tables = None
        self.nameMatcher = NameMatcher(high_confidence_threshold=75, medium_confidence_threshold=55, min_confidence=35)
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
               field['id'] != primaryFieldId:
                     _field = copy.deepcopy(field)
                     fields.append(_field)
        
        return fields
    

    def api_post(self, baseUrl=None, body=None, dictBody=None, tableId="", params=None, headers=None):

        url = os.path.join(baseUrl, tableId) if tableId else baseUrl
        self.logger.debug(f'API: Sending POST to endpoint \"{url}\" with:\n headers {headers} body: {body} dictBody: {dictBody} uriParams {params}')
        response = requests.post(url, data=body, json=dictBody, params=params, headers=headers)#, cert=self.cert)
        
        if (response.status_code != 200):
            self.logger.error(f'API: POST to tableId \"{tableId}\" with payload {body} returned status code {response.status_code} response: {response.text}')

        return response
        
    def api_get(self, baseUrl=None, body=None, tableId="", params=None, headers=None):

        url = os.path.join(baseUrl, tableId) if tableId else baseUrl
        self.logger.debug(f'API: Sending GET to endpoint \"{url}\" with:\n headers {headers} body: {body} uriParams {params}')
        
        response = requests.get(url, data=body, params=params, headers=headers)
        
        
        if (response.status_code != 200):
            self.logger.error(f'API: GET to endpoint \"{url}\" with payload {body} returned status code {response.status_code} response: {response.text}')

        return response


    def __retreive_all_tables_schema(self):
        authHeader = f'Bearer {self.apiKey}'
        _headers = {
                      'Authorization': authHeader
                   }
        response = self.api_get(self.tablesSchemaUrl, headers=_headers)
        data = response.json()  # Convert the JSON response to a dictionary
        self.tables = data.get("tables", []) 
        return self.tables
    
    def create_table(self, table:dict):
        authHeader = f'Bearer {self.apiKey}'
        _headers = {
                      'Authorization': authHeader,
                      'Content-Type': 'application/json'
                   }
        response = self.api_post(baseUrl= self.tablesSchemaUrl, dictBody=table, headers=_headers)
        return response.json()
        

    def load_tables(self):
        if not self.tables:
            tables = self.__retreive_all_tables_schema()
            self.tables = {}
            self.tableEmrSchemas: Dict[str, AirtableSchema] = {}
            # Traverse the tables and create writable schema
            for table in tables:
                # add the table to the tables dictionary
                tableName = table['name']
                self.tables[tableName] = table
                # Check if the table is in not in READONLY_TABLES
                
                is_person_table = tableName in self.PERSON_TABLES
                # if tableName not in self.READONLY_TABLES:
                # Create writeable schema by copy from table
                writeableSchema = copy.deepcopy(table)
                # replace the fields with the writable fields
                writeableSchema['fields'] = self.__writable_fields(table)
                # create the EmrTableSchema object
                is_person_table = tableName in self.PERSON_TABLES
                emrSchema = AirtableSchema(table_name=tableName, table_schema=writeableSchema, is_person_table=is_person_table)
                # add the EmrTableSchema to the tableWriteableSchemas dictionary
                self.logger.debug(f'Created writable schema for table {tableName}')
                self.tableEmrSchemas[tableName] = emrSchema
            
            # register sections
            for tableName, sections in self.TABLE_SECTIONS.items():
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
        return SpeakCareEmr.EMR_TABLES
    
    
    def get_emr_table_section_names(self, tableName=None):
        if not tableName:
            return None
        return SpeakCareEmr.TABLE_SECTIONS.get(tableName)

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
        return tableName in self.TABLE_SECTIONS
        
    def create_record(self, tableId, record):
        self.logger.debug(f'Creating record in table {tableId} with record {record}')
        record = self.api.table(self.appBaseId, tableId).create(record)
        if record:
            url = f'{self.webBaseUrl}{tableId}/{record["id"]}'
            return record, url
        else:
            self.logger.error(f'Failed to create record {record} in table {tableId}')
            return None, None
        
    def get_record(self, tableId, recordId):
        return self.api.table(self.appBaseId, tableId).get(recordId)
    
    def update_record(self, tableId, recordId, record):
        self.logger.debug(f'Update record in table {tableId} with record {record}')
        return self.api.table(self.appBaseId, tableId).update(record_id=recordId, fields=record)
    
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
        record['ParentRecord'] = [assessmentId]
        record['CreatedBy'] = [createdByNurseEmrId]
        self.logger.debug(f'Creating assessment section in table {sectionTableName} with record {record}')
        record, url = self.create_record(sectionTableName, record)
        return record, url, None
    
    def sign_assessment(self, assessmentTableName, assessmentId, signedByNurseEmrId):
        assessment = self.api.table(self.appBaseId, assessmentTableName).get(assessmentId)
        if assessment:
            record = {}
            record['Status'] = 'Completed'
            record['SignedBy'] = [signedByNurseEmrId]
            self.logger.debug(f'Sign assessment section in table {assessmentTableName} with record {record}')
            record = self.update_record(assessmentTableName, assessmentId, record)
            return record, None
        else:
            err_msg = f'sign_assessment: Failed to get assessment record with id {assessmentId}'
            self.logger.error(err_msg)
            return None, err_msg



# Patients methods
    def load_patients(self):
        # Load patients with structured name data (FirstName, LastName, Nickname)
        self.patientsTable = self.api.table(self.appBaseId, self.PATIENTS_TABLE)
        self.patientNamesDict = {}  # Structured format: {PatientID: {name: str, nickname: str, lastname: str}}
        self.patientEmrIds = []
        self.patientIds = []
        patients = self.patientsTable.all()
        for patient in patients:
            patient_id = patient['fields']['PatientID']
            first_name = patient['fields'].get('FirstName', '').strip()
            last_name = patient['fields'].get('LastName', '').strip()
            nickname = patient['fields'].get('Nickname', '').strip()  # Will be available in future
            
            # Store structured name data
            self.patientNamesDict[patient_id] = {
                'name': first_name,
                'nickname': nickname,
                'lastname': last_name
            }
            
            self.patientEmrIds.append(patient['id'])
            self.patientIds.append(patient_id)
        
        self.logger.debug(f'Loaded {len(self.patientNamesDict)} patients with structured names: {list(self.patientNamesDict.keys())}')

    def get_patients(self):
        return self.patientsTable.all()

    def get_patient_by_emr_id(self, patient_emr_id):
        return self.patientsTable.get(patient_emr_id)
    
    def get_patient_by_id(self, patient_id):
        for index, patienId in enumerate(self.patientIds): 
            if patient_id == patienId:
                patientEmdId = self.patientEmrIds[index]
                return self.patientsTable.get(patientEmdId)


    def __match_patient(self, patientName):
        match_result = self.nameMatcher.get_best_match(input_name=patientName, names_to_match=self.patientNamesDict)
        if match_result.primary_match and match_result.primary_match.confidence_score >= self.nameMatcher.min_confidence:
            primary_match = match_result.primary_match
            # Find the corresponding EMR ID for this patient ID
            try:
                patient_index = self.patientIds.index(primary_match.matched_id)
                patient_emr_id = self.patientEmrIds[patient_index]
                
                # Logging is handled by NameMatcher, just log the final result
                self.logger.debug(f"Patient match for '{patientName}': {primary_match.matched_name} ({primary_match.confidence_score:.1f}%)")
                
                return primary_match.matched_name, primary_match.matched_id, patient_emr_id
            except ValueError:
                self.logger.error(f"Patient ID {primary_match.matched_id} not found in patientIds list")
                return None, None, None
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
                # Get the full name from the structured data
                patient_data = self.patientNamesDict.get(patient_id, {})
                first_name = patient_data.get('name', '')
                last_name = patient_data.get('lastname', '')
                full_name = f"{first_name} {last_name}".strip()
                return full_name, self.patientEmrIds[index]
        return None, None

    def add_patient(self, patient):
        patient_name = patient.get('FullName')
        # Check if patient already exists by searching through patientNamesDict
        for patient_id, data in self.patientNamesDict.items():
            full_name = f"{data['name']} {data['lastname']}".strip()
            if patient_name == full_name:
                self.logger.warning(f"Patient '{patient_name}' already exists with id {patient_id}")
                return None
        
        patient_record = self.patientsTable.create(patient)
        if not patient_record:
            self.logger.error(f'Failed to create patient {patient}')
            return None
        else:
            # Add to structured data
            patient_id = patient_record['fields']['PatientID']
            first_name = patient_record['fields'].get('FirstName', '').strip()
            last_name = patient_record['fields'].get('LastName', '').strip()
            nickname = patient_record['fields'].get('Nickname', '').strip()
            
            self.patientNamesDict[patient_id] = {
                'name': first_name,
                'nickname': nickname,
                'lastname': last_name
            }
            self.patientEmrIds.append(patient_record['id'])
            self.patientIds.append(patient_id)
            self.logger.info(f"Created patient '{patient_name}' with id PatientID '{patient_id}")
            return patient_record

    def update_patient(self, patientEmrId, patient):
        self.logger.debug(f'Updating patient {patientEmrId} with {patient}')
        return self.patientsTable.update(patientEmrId, patient)

    def delete_patient(self, patientEmrId):
        try:
            idx = self.patientEmrIds.index(patientEmrId)
            recDeleted = self.patientsTable.delete(patientEmrId)
            patient_id = self.patientIds[idx]
            
            # Remove from all data structures
            self.patientIds.pop(idx)
            self.patientEmrIds.pop(idx)
            if patient_id in self.patientNamesDict:
                del self.patientNamesDict[patient_id]
            return recDeleted
        except Exception as e:
            self.logger.error(f'Failed to delete patient {patientEmrId} with error {e}')
            return None

# Nurses methods 
    def load_nurses(self):
        self.nursesTable = self.api.table(self.appBaseId, self.NURSES_TABLE)
        self.nurseNamesDict = {}  # Structured format: {NurseID: {name: str, nickname: str, lastname: str}}
        self.nurseEmrIds = []
        self.nurseIds = []
        nurses = self.nursesTable.all()
        for nurse in nurses:
            nurse_id = nurse['fields']['NurseID']
            # For nurses, 'Name' field might contain full name - we'll parse it
            full_name = nurse['fields'].get('Name', '').strip()
            first_name = nurse['fields'].get('FirstName', '').strip()
            last_name = nurse['fields'].get('LastName', '').strip()
            nickname = nurse['fields'].get('Nickname', '').strip()  # Will be available in future
            
            # If we don't have separate FirstName/LastName, parse the full Name field
            if not first_name and not last_name and full_name:
                name_parts = full_name.split()
                if len(name_parts) >= 2:
                    first_name = name_parts[0]
                    last_name = ' '.join(name_parts[1:])
                elif len(name_parts) == 1:
                    first_name = name_parts[0]
            
            # Store structured name data
            self.nurseNamesDict[nurse_id] = {
                'name': first_name,
                'nickname': nickname,
                'lastname': last_name
            }
            
            self.nurseEmrIds.append(nurse['id'])
            self.nurseIds.append(nurse_id)
        
        self.logger.debug(f'Loaded {len(self.nurseNamesDict)} nurses with structured names: {list(self.nurseNamesDict.keys())}')

    def get_nurses(self):
        return self.nursesTable.all()
    
    def get_nurse_by_emr_id(self, nurse_emr_id):
        return self.nursesTable.get(nurse_emr_id)
    
    def get_nurse_by_id(self, nurse_id):
        for index, nurseId in enumerate(self.nurseIds): 
            if nurse_id == nurseId:
                nurseEmrId = self.nurseEmrIds[index]
                return self.nursesTable.get(nurseEmrId)
    
    def __match_nurse(self, nurseName):
        match_result = self.nameMatcher.get_best_match(input_name=nurseName, names_to_match=self.nurseNamesDict)
        if match_result.primary_match and match_result.primary_match.confidence_score >= self.nameMatcher.min_confidence:
            primary_match = match_result.primary_match
            # Find the corresponding EMR ID for this nurse ID
            try:
                nurse_index = self.nurseIds.index(primary_match.matched_id)
                nurse_emr_id = self.nurseEmrIds[nurse_index]
                
                # Logging is handled by NameMatcher, just log the final result
                self.logger.debug(f"Nurse match for '{nurseName}': {primary_match.matched_name} ({primary_match.confidence_score:.1f}%)")
                
                return primary_match.matched_name, primary_match.matched_id, nurse_emr_id
            except ValueError:
                self.logger.error(f"Nurse ID {primary_match.matched_id} not found in nurseIds list")
                return None, None, None
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
                # Get the full name from the structured data
                nurse_data = self.nurseNamesDict.get(nurse_id, {})
                first_name = nurse_data.get('name', '')
                last_name = nurse_data.get('lastname', '')
                full_name = f"{first_name} {last_name}".strip()
                return full_name, self.nurseEmrIds[index]
        return None, None
    
    def get_nurses_table_json_schema(self):
        return self.get_table_json_schema(tableName=self.NURSES_TABLE)

    def add_nurse(self, nurse):
        nurse_name = nurse.get('Name')
        # Check if nurse already exists by searching through nurseNamesDict
        for nurse_id, data in self.nurseNamesDict.items():
            full_name = f"{data['name']} {data['lastname']}".strip()
            if nurse_name == full_name:
                self.logger.warning(f"Nurse '{nurse_name}' already exists with id {nurse_id}")
                return None
        
        nurse_record = self.nursesTable.create(nurse)
        if not nurse_record:
            self.logger.error(f'Failed to create nurse {nurse}')
            return None
        else:
            # Add to structured data
            nurse_id = nurse_record['fields']['NurseID']
            # Parse the Name field to get first/last names
            full_name = nurse_record['fields'].get('Name', '').strip()
            first_name = nurse_record['fields'].get('FirstName', '').strip()
            last_name = nurse_record['fields'].get('LastName', '').strip()
            nickname = nurse_record['fields'].get('Nickname', '').strip()
            
            # If we don't have separate FirstName/LastName, parse the full Name field
            if not first_name and not last_name and full_name:
                name_parts = full_name.split()
                if len(name_parts) >= 2:
                    first_name = name_parts[0]
                    last_name = ' '.join(name_parts[1:])
                elif len(name_parts) == 1:
                    first_name = name_parts[0]
            
            self.nurseNamesDict[nurse_id] = {
                'name': first_name,
                'nickname': nickname,
                'lastname': last_name
            }
            self.nurseEmrIds.append(nurse_record['id'])
            self.nurseIds.append(nurse_id)
            self.logger.info(f"Created nurse '{nurse_name}' with id NurseID '{nurse_id}")
            return nurse_record
    
    def update_nurse(self, nurseEmrId, nurse):
        self.logger.debug(f'Updating nurse {nurseEmrId} with {nurse}')
        return self.nursesTable.update(nurseEmrId, nurse)
    
    def delete_nurse(self, nurseEmrId):
        try:
            idx = self.nurseEmrIds.index(nurseEmrId)
            recDeleted = self.nursesTable.delete(nurseEmrId)
            nurse_id = self.nurseIds[idx]
            
            # Remove from all data structures
            self.nurseIds.pop(idx)
            self.nurseEmrIds.pop(idx)
            if nurse_id in self.nurseNamesDict:
                del self.nurseNamesDict[nurse_id]
            return recDeleted
        except Exception as e:
            self.logger.error(f'Failed to delete nurse {nurseEmrId} with error {e}')
            return None
    
    
    def get_nurse_patients(self, nurse_id):
        return self.nursesTable.get(nurse_id)['fields']['Patients']
    

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
            baseId = config.get('baseId')
            logger = config.get('logger')
            __singletonInstance = SpeakCareEmr(baseId=baseId, logger=logger)
    return __singletonInstance