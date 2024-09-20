import os
from pyairtable import Api as AirtableApi
import json
import logging
import requests
import time
from name_matching import NameMatcher
from dotenv import load_dotenv
from airtable_schema import AirtableSchema
import copy
from typing import Dict

# Load the .env file
load_dotenv()

APP_BASE_ID = 'appRFbM7KJ2QwCDb6'

class SpeakCareEmr:

    # Table names

    ### People ###
    PATIENTS_TABLE = 'Patients'
    NURSES_TABLE = 'Nurses'
    DOCTORS_TABLE = 'Doctors'
    
    ### Medical Records ###
    WEIGHTS_TABLE = 'Weights'
    BLOOD_PRESSURES_TABLE = 'Blood Pressures'
    BLOOD_SUGARS_TABLE = 'Blood Sugars'
    HEIGHTS_TABLE = 'Heights'
    TEMPERATURES_TABLE = 'Temperatures'
    O2_SATURATIONS_TABLE = 'O2 Saturations'
    EPISODES_TABLE = 'Episodes'
    PROGRESS_NOTES_TABLE = 'Progress Notes'

    ### Assessments ###
    # Admission
    ADMISSION_ASSESSMENTS_TABLE = 'Admission'
    ADMISSION_SECTION_DEMOGRAPHCS_TABLE   = 'Admission: SECTION 1. DEMOGRAPHICS'
    ADMISSION_SECTION_VITALS_TABLE        = 'Admission: SECTION 2. VITALS-ALLERGIES'
    ADMISSION_SECTION_SKIN_TABLE          = 'Admission: SECTION 3. SKIN CONDITION'
    ADMISSION_SECTION_PHYSICAL_TABLE      = 'Admission: SECTION 4. PHYSICAL / ADL /COMMUNICATION STATUS'
    ADMISSION_SECTION_BOWEL_BLADDER_TABLE = 'Admission: SECTION 5. BOWEL-BLADDER EVALUATION'
    ADMISSION_SECTION_PSYCHOSOCIAL_TABLE  = 'Admission: SECTION 6. PSYCHOSOCIAL ASPECTS'
    ADMISSION_SECTION_DISCHARGE_TABLE     = 'Admission: SECTION 7. SECTION 7. DISCHARGE EVALUATION'
    ADMISSION_SECTION_FACILITY_TABLE      = 'Admission: SECTION 8. ORIENTATION TO FACILITY'

    # Fall Risk Screen
    FALL_RISK_SCREEN_TABLE = 'Fall Risk Screen'
    FALL_RISK_SCREEN_SECTION_1_TABLE = 'Fall Risk Screen: SECTION 1'

    # TODO: Table and sections names need to be loaded dyanically from the API
    EMR_TABLES = [
        WEIGHTS_TABLE, 
        BLOOD_PRESSURES_TABLE, 
        BLOOD_SUGARS_TABLE, 
        HEIGHTS_TABLE, 
        TEMPERATURES_TABLE,
        O2_SATURATIONS_TABLE, 
        EPISODES_TABLE, 
        PROGRESS_NOTES_TABLE,
        ADMISSION_ASSESSMENTS_TABLE,
        FALL_RISK_SCREEN_TABLE
    ]

    TABLE_SECTIONS = { 
            ADMISSION_ASSESSMENTS_TABLE: [
                ADMISSION_SECTION_DEMOGRAPHCS_TABLE, 
                ADMISSION_SECTION_VITALS_TABLE, 
                ADMISSION_SECTION_SKIN_TABLE, 
                ADMISSION_SECTION_PHYSICAL_TABLE, 
                ADMISSION_SECTION_BOWEL_BLADDER_TABLE, 
                ADMISSION_SECTION_PSYCHOSOCIAL_TABLE,
                ADMISSION_SECTION_FACILITY_TABLE
            ],            
            FALL_RISK_SCREEN_TABLE: [FALL_RISK_SCREEN_SECTION_1_TABLE]
    }

    METADATA_BASE_URL = 'https://api.airtable.com/v0/meta/bases'
    API_BASE_URL = 'https://api.airtable.com/v0'
    WEB_APP_BASE_URL = 'https://airtable.com'

    
    READONLY_TABLES = [PATIENTS_TABLE, NURSES_TABLE, DOCTORS_TABLE]
    INTERNAL_FIELDS = ['Patient', 'CreatedBy', 'Doctor', 'SpeakCare']
    READONLY_FIELD_TYPES = ['autoNumber', 'barcode', 'button', 'collaborator', 'count', 'createdBy',  'createdTime', 
                            'formula', 'lastModifiedTime', 'lastModifiedBy', 'multipleCollaborators', 'multipleLookupValues',
                            'multipleRecordLinks', 'rollup', 'singleCollaborator']

    def __init__(self, baseId: str, logger: logging.Logger):
        self.apiKey = os.getenv('AIRTABLE_API_KEY')
        self.api = AirtableApi(self.apiKey)
        self.appBaseId = baseId
        self.logger = logger
        self.tablesSchemaUrl = f'{self.METADATA_BASE_URL}/{baseId}/tables/'
        self.apiBaseUrl = f'{self.API_BASE_URL}/{baseId}/'
        self.webBaseUrl = f'{self.WEB_APP_BASE_URL}/{baseId}/'
        self.tables = None
        self.nameMatcher = NameMatcher(primary_threshold=90, secondary_threshold=70)
        self.initialze()

    def initialze(self):
        self.load_tables()
        self.load_patients()
        self.load_nurses()
    


    def __external_writable_schema(self, tableSchema):
        fields = []
        primaryFieldId = tableSchema['primaryFieldId']
        for field in tableSchema['fields']:
            if field['name'] not in self.INTERNAL_FIELDS and\
               field['type'] not in self.READONLY_FIELD_TYPES and\
               field['id'] != primaryFieldId:
                     _field = copy.deepcopy(field)
                     fields.append(_field)
        return fields
    

    def api_post(self, baseUrl=None, body=None, tableId="", params=None, headers=None):

        url = baseUrl + tableId
        self.logger.debug(f'API: Sending POST to endpoint \"{url}\" with:\n headers {headers} body: {body} uriParams {params}')
        response = requests.post(url, data=body, params=params, headers=headers, cert=self.cert)
        
        time.sleep(0.2)
        if (response.status_code != 200):
            self.logger.error(f'API: POST to tableId \"{tableId}\" with payload {body} returned status code {response.status_code} response: {response.text}')

        return response
        
    def api_get(self, baseUrl=None, body=None, tableId="", params=None, headers=None):

        url = baseUrl + tableId
        self.logger.debug(f'API: Sending GET to endpoint \"{url}\" with:\n headers {headers} body: {body} uriParams {params}')
        
        time.sleep(0.2)
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
    
    def load_tables(self):
        if not self.tables:
            tables = self.__retreive_all_tables_schema()
            #self.tables = self.__retreive_all_tables_schema()
            self.tables = {}
            self.tableWriteableSchemas: Dict[str, AirtableSchema] = {}
            # Traverse the tables and create writable schema
            for table in tables:
                # add the table to the tables dictionary
                tableName = table['name']
                self.tables[tableName] = table
                # Check if the table is in not in READONLY_TABLES
                if tableName not in self.READONLY_TABLES:
                    # Create writeable schema by copy from table
                    writeableSchema = copy.deepcopy(table)
                    # replace the fields with the writable fields
                    writeableSchema['fields'] = self.__external_writable_schema(table)
                    # create the EmrTableSchema object
                    emrSchema = AirtableSchema(table_name=tableName, table_schema=writeableSchema)
                    # add the EmrTableSchema to the tableWriteableSchemas dictionary
                    self.logger.debug(f'Created writable schema for table {tableName}')
                    self.tableWriteableSchemas[tableName] = emrSchema
        
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

    def get_table_schema(self, tableId=None, tableName=None):
        if tableName:
            return self.tables.get(tableName)
        elif tableId:
            for table in self.tables:
                if table['id'] == tableId:
                    return table
        else:
            return None
        
    
    def get_record_writable_schema(self, tableId=None, tableName=None):
        if not tableId and not tableName:
            self.logger.warning(f'get_table_writable_schema: tableId and tableName are None')
            return None
        
        if tableId and not tableName:
            tableName = self.get_table_name(tableId)
            if not tableName:
                self.logger.warning(f'get_table_writable_schema: Table {tableId} not found')
                return None

        if tableName in self.READONLY_TABLES:
            self.logger.warning(f'get_table_writable_schema: Table {tableName} is readonly')
            return None
        
        tableSchema = self.tableWriteableSchemas.get(tableName)

        if not tableSchema:
            self.logger.error(f'get_table_writable_schema: Table {tableName} failed to get schema')
            return None

        if tableSchema.get_name() != tableName:
            error_message = f'get_table_writable_schema: Table {tableSchema.get_name()} is different from {tableName}'
            self.logger.error(error_message)
            raise ValueError(error_message)
        
        return tableSchema.get_schema()


    def create_record(self, tableId, record):
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
        return self.api.table(self.appBaseId, tableId).update(record_id=recordId, fields=record)
    
    def validate_record(self, tableName, record, errors):
        tableSchema = self.tableWriteableSchemas.get(tableName)
        valid_fields = {}
        if not tableSchema:
            errors.append(f'validate_record: Failed to get writable schema for table {tableName}')
            return False, {}
        
        isValidRecord, valid_fields = tableSchema.validate_record(record=record, errors= errors)
        if not isValidRecord:
            errors.append(f'validate_record: Invalid record {record} for table {tableName}.')
            return False, valid_fields
        
        return True, valid_fields
    
    def validate_partial_record(self, tableName, record, errors):
        tableSchema = self.tableWriteableSchemas.get(tableName)
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
        

    def create_medical_record(self, tableName, record, 
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


    def create_assessment(self, assessmentTableName, record, patientEmrId, createdByNurseEmrId, errors=[]):
        
        isValidRecord, valid_fields = self.validate_record(tableName=assessmentTableName, record=record, errors=errors)
        if not isValidRecord:
            err_msg = f'create_assessment: Invalid record {record} for table {assessmentTableName}.'
            errors.append(err_msg)
            self.logger.error(err_msg)
            return None, None, err_msg        
                
        record['Patient'] = [patientEmrId]
        record['CreatedBy'] = [createdByNurseEmrId]
        record['SpeakCare'] = 'Draft'
        status = record.get('Status')
        if not status:
            record['Status'] = 'In Progress'
        record, url = self.create_record(assessmentTableName, record)
        return record, url, None
    
    def create_assessment_section(self, sectionTableName, record, 
                                  assessmentId, createdByNurseEmrId, errors=[]):
        
        isValidRecord, valid_fields = self.validate_record(tableName=sectionTableName, record=record, errors=errors)
        if not isValidRecord:
            err_msg = f'create_assessment_section: Invalid record {record} for table {sectionTableName}.'
            errors.append(err_msg)
            self.logger.error(err_msg)
            return None, None, err_msg         

        record['ParentRecord'] = [assessmentId]
        record['CreatedBy'] = [createdByNurseEmrId]
        record, url = self.create_record(sectionTableName, record)
        return record, url, None
    
    def sign_assessment(self, assessmentTableName, assessmentId, signedByNurseEmrId):
        assessment = self.api.table(self.appBaseId, assessmentTableName).get(assessmentId)
        if assessment:
            record = {}
            record['Status'] = 'Completed'
            record['SignedBy'] = [signedByNurseEmrId]
            record = self.update_record(assessmentTableName, assessmentId, record)
            return record, None
        else:
            err_msg = f'sign_assessment: Failed to get assessment record with id {assessmentId}'
            self.logger.error(err_msg)
            return None, err_msg



# Patients methods
    def load_patients(self):
        self.patientsTable = self.api.table(self.appBaseId, self.PATIENTS_TABLE)
        self.patientNames=[]
        self.patientEmrIds=[]
        self.patientIds=[]
        patients = self.patientsTable.all()
        for patient in patients:
            self.patientNames.append(patient['fields']['FullName'])
            self.patientEmrIds.append(patient['id'])
            self.patientIds.append(patient['fields']['PatientID'])
        self.logger.debug(f'Loaded patients. Patients names: {self.patientNames}')

    def get_patients(self):
        return self.patientsTable.all()

    def get_patient_by_emr_id(self, patient_emr_id):
        return self.patientsTable.get(patient_emr_id)
    
    def get_patient_by_id(self, patient_id):
        for index, patienId in enumerate(self.patientIds): 
            if patient_id == patienId:
                patientEmdId = self.patientEmrIds[index]
                return self.patientsTable.get(patientEmdId)


    def __lookup_patient(self, patientName):
        matchedName, matchedIndex, score = self.nameMatcher.get_best_match(input_name= patientName, names_to_match= self.patientNames)
        if matchedName:
            return matchedName, self.patientIds[matchedIndex], self.patientEmrIds[matchedIndex]
        else:
            return None, None, None
    
    def lookup_patient(self, patientFullName):
        matchedName, patientId, patientEmrId = self.__lookup_patient(patientFullName)
        if not matchedName:
            self.logger.info(f'Patient {patientFullName} not found')
        return matchedName, patientId, patientEmrId
    
    def lookup_patient_by_id(self, patient_id):
        for index, patienId in enumerate(self.patientIds): 
            if patient_id == patienId:
                return self.patientNames[index], self.patientEmrIds[index]
        return None, None
    
    def add_patient(self, patient):
        return self.patientsTable.create(patient)

    def update_patient(self, patient_id, patient):
        return self.patientsTable.update(patient_id, patient)

    def delete_patient(self, patient_id):
        return self.patientsTable.delete(patient_id)

# Nurses methods 
    def load_nurses(self):
        self.nursesTable = self.api.table(self.appBaseId, self.NURSES_TABLE)
        self.nurseNames = []
        self.nurseEmrIds = []
        self.nurseIds = []
        nurses = self.nursesTable.all()
        for nurse in nurses:
            self.nurseNames.append(nurse['fields']['Name'])
            self.nurseEmrIds.append(nurse['id'])
            self.nurseIds.append(nurse['fields']['NurseID'])
        self.logger.debug(f'Loaded nurses. Nurses names: {self.nurseNames}')

    def get_nurses(self):
        return self.nursesTable.all()
    
    def get_nurse_by_emr_id(self, nurse_emr_id):
        return self.nursesTable.get(nurse_emr_id)
    
    def get_nurse_by_id(self, nurse_id):
        for index, nurseId in enumerate(self.nurseIds): 
            if nurse_id == nurseId:
                nurseEmdId = self.nurseEmrIds[index]
                return self.nursesTable.get(nurseEmdId)
    
    def __lookup_nurse(self, nurseName):
        matchedName, matchedIndex, score = self.nameMatcher.get_best_match(input_name=  nurseName, names_to_match=  self.nurseNames)
        if matchedName:
            return matchedName, self.nurseIds[matchedIndex], self.nurseEmrIds[matchedIndex]
        else:
            return None, None, None
        
    def lookup_nurse(self, nurseName):
        matchedName, nurseId, nurseEmrId = self.__lookup_nurse(nurseName)
        if not matchedName:
            self.logger.info(f'Nurse {nurseName} not found')
        return matchedName, nurseId, nurseEmrId
    
    def lookup_nurse_by_id(self, nurse_id):
        for index, nurseId in enumerate(self.nurseIds): 
            if nurse_id == nurseId:
                return self.nurseNames[index], self.nurseEmrIds[index]
        return None, None
    
    def add_nurse(self, nurse):
        return self.nursesTable.create(nurse)
    
    def update_nurse(self, nurse_id, nurse):
        return self.nursesTable.update(nurse_id, nurse)
    
    def delete_nurse(self, nurse_id):
        return self.nursesTable.delete(nurse_id)
    
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