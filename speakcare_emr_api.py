import os
from pyairtable import Api as AirtableApi
import json
import logging
import requests
import time
from name_matching import NameMatcher

APP_BASE_ID = 'appRFbM7KJ2QwCDb6'

class SpeakCareEmrApi:

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
    ADMISSION_SECTION_1_TABLE = 'Admission: SECTION 1. DEMOGRAPHICS'
    ADMISSION_SECTION_2_TABLE = 'Admission: SECTION 2. VITALS-ALLERGIES'
    ADMISSION_SECTION_3_TABLE = 'Admission: SECTION 3. SKIN CONDITION'
    ADMISSION_SECTION_4_TABLE = 'Admission: SECTION 4. PHYSICAL / ADL /COMMUNICATION STATUS'
    ADMISSION_SECTION_5_TABLE = 'Admission: SECTION 5. BOWEL-BLADDER EVALUATION'
    ADMISSION_SECTION_6_TABLE = 'Admission: SECTION 6. PSYCHOSOCIAL ASPECTS'
    ADMISSION_SECTION_7_TABLE = 'Admission: SECTION 7. SECTION 7. DISCHARGE EVALUATION'
    ADMISSION_SECTION_8_TABLE = 'Admission: SECTION 8. ORIENTATION TO FACILITY'

    # Fall Risk Screen
    FALL_RISK_SCREEN_TABLE = 'Fall Risk Screen'
    FALL_RISK_SCREEN_SECTION_1_TABLE = 'Fall Risk Screen: SECTION 1'

    METADATA_BASE_URL = 'https://api.airtable.com/v0/meta/bases'
    API_BASE_URL = 'https://api.airtable.com/v0'
    WEB_APP_BASE_URL = 'https://airtable.com'
    
    READONLY_TABLES = [PATIENTS_TABLE, NURSES_TABLE, DOCTORS_TABLE]
    FILTER_FIELDS = ['Patient', 'CreatedBy', 'Doctor']
    READONLY_FIELD_TYPES = ['autoNumber', 'barcode', 'button', 'collaborator', 'count', 'createdBy',  'createdTime', 
                            'formula', 'lastModifiedTime', 'lastModifiedBy', 'multipleCollaborators', 'multipleLookupValues',
                            'multipleRecordLinks', 'rollup', 'singleCollaborator']

    def __init__(self, baseId: str, logger: logging.Logger):
        self.apiKey = os.environ['AIRTABLE_API_KEY']
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

    def __user_writable_fields(self, tableSchema):
        fields = []
        primaryFieldId = tableSchema['primaryFieldId']
        for field in tableSchema['fields']:
            if field['name'] not in self.FILTER_FIELDS and\
               field['type'] not in self.READONLY_FIELD_TYPES and\
               field['id'] != primaryFieldId:
                     fields.append(field)
        return fields
    

    def api_post(self, baseUrl=None, body=None, tableId="", params=None, headers=None):

        url = baseUrl + tableId
        self.logger.log(logging.DEBUG, f'API: Sending POST to endpoint \"{url}\" with:\n headers {headers} body: {body} uriParams {params}')
        #response = self.session.post(url, data=_body, params=_params, headers=_headers, cert=self.cert)
        response = requests.post(url, data=body, params=params, headers=headers, cert=self.cert)
        
        time.sleep(0.2)
        if (response.status_code != 200):
            self.logger.log(logging.ERROR, f'API: POST to tableId \"{tableId}\" with payload {body} returned status code {response.status_code} response: {response.text}')

        return response
        
    def api_get(self, baseUrl=None, body=None, tableId="", params=None, headers=None):

        url = baseUrl + tableId
        self.logger.log(logging.DEBUG, f'API: Sending GET to endpoint \"{url}\" with:\n headers {headers} body: {body} uriParams {params}')
        
        time.sleep(0.2)
        response = requests.get(url, data=body, params=params, headers=headers)
        
        
        if (response.status_code != 200):
            self.logger.log(logging.ERROR, f'API: GET to endpoint \"{url}\" with payload {body} returned status code {response.status_code} response: {response.text}')

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
            self.tables = self.__retreive_all_tables_schema()
        return self.tables
    
    def get_table_id(self, tableName):
        tables = self.load_tables()
        for table in tables:
            if table['name'] == tableName:
                return table['id']
        return None
    
    def get_table_name(self, tableId):
        tables = self.load_tables()
        for table in tables:
            if table['id'] == tableId:
                return table['name']
        return None

    def get_table_schema(self, tableId=None, tableName=None):
        tables = self.load_tables()
        for table in tables:
            if tableId:
                if table['id'] == tableId:
                    return table
            elif tableName:
                if table['name'] == tableName:
                    return table
        return None
    
    def get_record_external_schema(self, tableId=None, tableName=None):
        if not tableId and not tableName:
            self.logger.log(logging.ERROR, f'get_table_writable_fields: tableId and tableName are None')
            return None

        if tableName in self.READONLY_TABLES:
            self.logger.log(logging.INFO, f'get_table_writable_fields: Table {tableName} is readonly')
            return None
        
        tableSchema = self.get_table_schema(tableId=tableId, tableName=tableName)

        if not tableSchema:
            self.logger.log(logging.ERROR, f'get_table_writable_fields: Table {tableName} failed to get schema')
            return None

        if tableSchema['name'] in self.READONLY_TABLES:
            self.logger.log(logging.INFO, f'get_table_writable_fields: Table {tableSchema["name"]} is readonly')
            return None
        
        return self.__user_writable_fields(tableSchema)


    def create_record(self, tableId, record):
        record = self.api.table(self.appBaseId, tableId).create(record)
        if record:
            url = f'{self.webBaseUrl}{tableId}/{record["id"]}'
            return record, url
        else:
            self.logger.log(logging.ERROR, f'Failed to create record {record} in table {tableId}')
            return None, None
    
    def update_record(self, tableId, recordId, record):
        return self.api.table(self.appBaseId, tableId).update(record_id=recordId, fields=record)

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
                              patientId=None, createdByNurseId=None):
        if patientId:
            record['Patient'] = [patientId]
        if createdByNurseId:
            record['CreatedBy'] = [createdByNurseId]
        tableId = self.get_table_id(tableName)
        return self.create_record(tableId= tableId, record=record)


    def create_assessment(self, assessmentTableName, patientId, createdByNurseId):
        record = {}
        record['Patient'] = [patientId]
        record['CreatedBy'] = [createdByNurseId]
        record['Status'] = 'In Progress'
        return self.create_record(assessmentTableName, record)
    
    def create_assessment_section(self, sectionTableName, record, 
                                  assessmentId=None, createdByNurseId=None):

        if assessmentId:
            record['Assessment'] = [assessmentId]
        if createdByNurseId:
            record['CreatedBy'] = [createdByNurseId]
        return self.create_record(sectionTableName, record)
    
    def sign_assessment(self, assessmentTableName, assessmentId, signedByNurseId):
        assessment = self.api.table(self.appBaseId, assessmentTableName).get(assessmentId)
        if assessment:
            record = {}
            record['Status'] = 'Completed'
            record['SignedBy'] = [signedByNurseId]
            return self.update_record(assessmentTableName, assessmentId, record)
        else:
            self.logger.log(logging.ERROR, f'Failed to get assessment record with id {assessmentId}')
            return None



# Patients methods
    def load_patients(self):
        self.patientsTable = self.api.table(self.appBaseId, self.PATIENTS_TABLE)
        self.patientNames = [patient['fields']['FullName'] for patient in self.patientsTable.all()]
        self.patientIds = [patient['id'] for patient in self.patientsTable.all()]
        self.logger.info(f'Loaded patients. Patients names: {self.patientNames}')

    def get_patients(self):
        return self.patientsTable.all()

    def get_patient(self, patient_id):
        return self.patientsTable.get(patient_id)
    
    def lookup_patient(self, patientFullName):
        matchedName, matchedIndex, score = self.nameMatcher.get_best_match(input_name= patientFullName, names_to_match= self.patientNames)
        if matchedName:
            return matchedName, self.patientIds[matchedIndex]
        else:
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
        self.nurseNames = [nurse['fields']['Name'] for nurse in self.nursesTable.all()]
        self.nurseIds = [nurse['id'] for nurse in self.nursesTable.all()]
        self.logger.info(f'Loaded nurses. Nurses names: {self.nurseNames}')

    def get_nurses(self):
        return self.nursesTable.all()
    
    def get_nurse(self, nurse_id):
        return self.nursesTable.get(nurse_id)
    
    def lookup_nurse(self, nurseName):
        matchedName, matchedIndex, score = self.nameMatcher.get_best_match(input_name=  nurseName, names_to_match=  self.nurseNames)
        if matchedName:
            return matchedName, self.nurseIds[matchedIndex]
        else:
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
            __singletonInstance = SpeakCareEmrApi(baseId=baseId, logger=logger)
    return __singletonInstance