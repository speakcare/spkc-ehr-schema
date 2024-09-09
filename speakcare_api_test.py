import sys
import os
from pyairtable import Api as AirtableApi
import json
from enum import Enum
import logging
import requests
import time


APP_BASE_ID = 'appRFbM7KJ2QwCDb6'
PATIENTS_TABLE_ID = 'tbleNsgzYZvRy1st1'
NURSES_TABLE_ID = 'tblku5F04AH4D9WBo'

# api = Api(os.environ['AIRTABLE_API_KEY'])
# patientsTable = api.table(APP_BASE_ID, PATIENTS_TABLE_ID)
# patients = patientsTable.all()


# #patientsJson =  json.loads(patients)
# print(f'patients: {json.dumps(patients, indent=4)}')


class WeightRecord:

    WEIGHTS_TABLE_ID = 'tbl7h1M2HkAE3BI0l'
    class WeightUnits(Enum):
        Lbs = 'Lbs'
        Kg= 'Kg'
    
    class WeightScale(Enum):
        Standing = 'Standing'
        Wheelchair = 'Wheelchair'
        Sitting = 'Sitting'
        Bath = 'Bath'
        Bed = 'Bed'
        MechanicalLift = 'Mechanical Lift'
        Hoyer = 'Hoyer'

    def __init__(self, patientId, nurseId,  weight, units: WeightUnits = WeightUnits.Lbs , 
                 scale: WeightScale = WeightScale.Standing):
        
        self.patientId = patientId
        self.createdBy = nurseId
        self.weight = weight
        self.units = units
        self.scale = scale
    
    def __str__(self):
        return f'patientId: {self.patientId}, createdBy: {self.createdBy}, weight: {self.weight}, units: {self.units.value}, scale: {self.scale.value}'
    
    def __repr__(self):
        return self.__str__()
    
    def to_dict(self):
         return {
                    "Patient": [self.patientId],
                    "CreatedBy": [self.createdBy],
                    "Units": self.units.value,
                    "Weight": self.weight,
                    "Scale": self.scale.value
                }
    
    def to_json(self):
        return json.dumps(self.to_dict())
    


class SpeakCareEmrApi:


    PATIENTS_TABLE = 'Patients'
    NURSES_TABLE = 'Nurses'
    DOCTORS_TABLE = 'Doctors'
    WEIGHTS_TABLE = 'Weights'
    BLOOD_PRESSURES_TABLE = 'Blood Pressures'
    BLOOD_SUGARS_TABLE = 'Blood Sugars'
    HEIGHTS_TABLE = 'Heights'
    TEMPERATURES_TABLE = 'Temperatures'
    O2_SATURATIONS_TABLE = 'O2 Saturations'
    EPISODES_TABLE = 'Episodes'
    ADMISSION_ASSESSMENTS_TABLE = 'Admission Assessments'
    FALL_RISK_SCREEN_TABLE = 'Fall Risk Screen'
    PROGRESS_NOTES_TABLE = 'Progress Notes'
    ADMISSION_SECTION_1_TABLE = 'Admission: SECTION 1. DEMOGRAPHICS'
    ADMISSION_SECTION_2_TABLE = 'Admission: SECTION 2. VITALS-ALLERGIES'
    ADMISSION_SECTION_3_TABLE = 'Admission: SECTION 3. SKIN CONDITION'
    ADMISSION_SECTION_4_TABLE = 'Admission: SECTION 4. PHYSICAL / ADL /COMMUNICATION STATUS'
    ADMISSION_SECTION_5_TABLE = 'Admission: SECTION 5. BOWEL-BLADDER EVALUATION'
    ADMISSION_SECTION_6_TABLE = 'Admission: SECTION 6. PSYCHOSOCIAL ASPECTS'
    ADMISSION_SECTION_7_TABLE = 'Admission: SECTION 7. SECTION 7. DISCHARGE EVALUATION'
    ADMISSION_SECTION_8_TABLE = 'Admission: SECTION 8. ORIENTATION TO FACILITY'

    METADATA_BASE_URL = 'https://api.airtable.com/v0/meta/bases'
    API_BASE_URL = 'https://api.airtable.com/v0'
    
    READONLY_TABLES = [PATIENTS_TABLE, NURSES_TABLE, DOCTORS_TABLE]
    FILTER_FIELDS = ['Patient', 'CreatedBy', 'Doctor']
    READONLY_FIELD_TYPES = ['autoNumber', 'barcode', 'button', 'collaborator', 'count', 'createdBy',  'createdTime', 
                            'formula', 'lastModifiedTime', 'lastModifiedBy', 'multipleCollaborators', 'multipleLookupValues',
                            'multipleRecordLinks', 'rollup', 'singleCollaborator']

    def __init__(self, baseId, logger: logging.Logger):
        self.apiKey = os.environ['AIRTABLE_API_KEY']
        self.api = AirtableApi(self.apiKey)
        self.appBaseId = baseId
        self.logger = logger
        self.tablesSchemaUrl = f'{self.METADATA_BASE_URL}/{baseId}/tables/'
        self.apiBaseUrl = f'{self.API_BASE_URL}/{baseId}/'

    def __user_writable_fields(self, tableSchema):
        fields = []
        primaryFieldId = tableSchema['primaryFieldId']
        for field in tableSchema['fields']:
            if field['name'] not in self.FILTER_FIELDS and\
               field['type'] not in self.READONLY_FIELD_TYPES and\
               field['id'] != primaryFieldId:
                     fields.append(field)
        return fields
    
    def get_all_tables_schema(self):
        #self.logger.log(logging.DEBUG, f'Sending POST to endpoint \"{url}\" with:\n headers {headers} body: {body} uriParams {params}')
        #response = self.session.post(url, data=_body, params=_params, headers=_headers, cert=self.cert)
        authHeader = f'Bearer {self.apiKey}'
        _headers = {
                      'Authorization': authHeader
                   }
        response = requests.get(self.tablesSchemaUrl,  headers=_headers)
        data = response.json()  # Convert the JSON response to a dictionary
        self.tables = data.get("tables", []) 
        #self.tables = response.json()
        return self.tables
    
    def get_table_schema(self, tableId=None, tableName=None):
        for table in self.tables:
            if tableId:
                if table['id'] == tableId:
                    return table
            elif tableName:
                if table['name'] == tableName:
                    return table
        return None
    
    def get_table_writable_fields(self, tableId=None, tableName=None):
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

    def api_post(self, body=None, tableId="", params=None, headers=None):

        url = self.apiBaseUrl + tableId
        self.logger.log(logging.DEBUG, f'API: Sending POST to endpoint \"{url}\" with:\n headers {headers} body: {body} uriParams {params}')
        #response = self.session.post(url, data=_body, params=_params, headers=_headers, cert=self.cert)
        response = requests.post(url, data=body, params=params, headers=headers, cert=self.cert)
        
        time.sleep(0.2)
        if (response.status_code != 200):
            self.logger.log(logging.ERROR, f'API: POST to tableId \"{tableId}\" with payload {body} returned status code {response.status_code} response: {response.text}')

        return response
        
    def api_get(self, body=None, tableId="", params=None, headers=None):

        url = self.apiBaseUrl + tableId
        self.logger.log(logging.DEBUG, f'API: Sending GET to endpoint \"{url}\" with:\n headers {headers} body: {body} uriParams {params}')
        
        time.sleep(0.2)
        response = requests.get(url, data=body, params=params, headers=headers)
        
        
        if (response.status_code != 200):
            self.logger.log(logging.ERROR, f'API: GET to endpoint \"{url}\" with payload {body} returned status code {response.status_code} response: {response.text}')

        return response

    def create_record(self, table_id, record):
        return self.api.table(APP_BASE_ID, table_id).create(record)
    
    def create_records_batch(self, table_id, records):
        return self.api.table(APP_BASE_ID, table_id).batch_create(records)
    
    def load_patients(self):
        self.patientsTable = self.api.table(APP_BASE_ID, PATIENTS_TABLE_ID)

    def get_patients(self):
        return self.patientsTable.all()

    def get_patient(self, patient_id):
        return self.patientsTable.get(patient_id)

    def add_patient(self, patient):
        return self.patientsTable.create(patient)

    def update_patient(self, patient_id, patient):
        return self.patientsTable.update(patient_id, patient)

    def delete_patient(self, patient_id):
        return self.patientsTable.delete(patient_id)
    
    def load_nurses(self):
        self.nursesTable = self.api.table(APP_BASE_ID, NURSES_TABLE_ID)

    def get_nurses(self):
        return self.nursesTable.all()
    
    def get_nurse(self, nurse_id):
        return self.nursesTable.get(nurse_id)
    
    def add_nurse(self, nurse):
        return self.nursesTable.create(nurse)
    
    def update_nurse(self, nurse_id, nurse):
        return self.nursesTable.update(nurse_id, nurse)
    
    def delete_nurse(self, nurse_id):
        return self.nursesTable.delete(nurse_id)
    
    def get_nurse_patients(self, nurse_id):
        return self.nursesTable.get(nurse_id)['fields']['Patients']
    
    def create_progress_note(self, patient_id, nurse_id,  progress_note):
        pass

    def create_weight(self, patient_id, nurse_id, weight):
        pass
        # return self.patientsTable.create_linked_record(patient_id, 'Weights', weight)

    def create_blood_pressure(self, patient_id, nurse_id, blood_pressure):
        pass
        # return self.patientsTable.create_linked_record(patient_id, 'Blood Pressures', blood_pressure)

    def create_blood_sugar(self, patient_id, nurse_id, blood_sugar):
        pass
        # return self.patientsTable.create_linked_record(patient_id, 'Blood Sugars', blood_sugar)

    def create_height(self, patient_id, nurse_id, height):
        pass
        # return self.patientsTable.create_linked_record(patient_id, 'Heights', height)

    def create_temperature(self, patient_id, nurse_id, temperature):
        pass
        # return self.patientsTable.create_linked_record(patient_id, 'Temperatures', temperature)
    
    def create_os_saturation(self, patient_id, nurse_id, os_saturation):
        pass
        # return self.patientsTable.create_linked_record(patient_id, 'Os Saturations', os_saturation)
    
    def create_episode(self, patient_id, nurse_id, eposide):
        pass
        # return self.patientsTable.create_linked_record(patient_id, 'Episodes', eposide)
    
    def create_assessment(self, patient_id, nurse_id, assessment):
        pass
        # return self.patientsTable.create_linked_record(patient_id, 'Assessments', assessment)

    def create_admission_assessment(self, patient_id, nurse_id, admission_assessment, section = {}):
        pass
        # return self.patientsTable.create_linked_record(patient_id, 'Admission Assess

    def create_fall_risk_screen_assessment(self, patient_id, nurse_id, fall_risk_screen_assessment):
        pass
        # return self.patientsTable.create_linked_record(patient_id, 'Fall Risk Screen Assessments', fall_risk_screen_assessment)


def main(argv):    

    # Initialize logging
    logging.basicConfig()
    #logging.getLogger().setLevel(logging.INFO)
    loggger = logging.getLogger("speackcare.emr.api")
    loggger.setLevel(logging.INFO)
    loggger.propagate = True

    APP_BASE_ID = 'appRFbM7KJ2QwCDb6'

    api = SpeakCareEmrApi(baseId=APP_BASE_ID, logger=loggger)
    api.get_all_tables_schema()
    # bloodPressuresTableSchema = api.get_table_schema(tableName=SpeakCareEmrApi.BLOOD_PRESSURES_TABLE)
    # bloodPressuresTableId = bloodPressuresTableSchema['id']
    # print(f'{SpeakCareEmrApi.BLOOD_PRESSURES_TABLE} Table schema: {json.dumps(bloodPressuresTableSchema, indent=4)}')
    # bloodPressuresTableSchema = api.get_table_schema(tableId=bloodPressuresTableId)
    # print(f'{SpeakCareEmrApi.BLOOD_PRESSURES_TABLE} Table schema: {json.dumps(bloodPressuresTableSchema, indent=4)}')

    # bloodPressuresTableWritableFields = api.get_table_writable_fields(tableId=bloodPressuresTableId)
    # print(f'{SpeakCareEmrApi.BLOOD_PRESSURES_TABLE} Table writable fields: {json.dumps(bloodPressuresTableWritableFields, indent=4)}')

    # fallsRiskScreenTableSchema = api.get_table_schema(tableName=SpeakCareEmrApi.FALL_RISK_SCREEN_TABLE)
    # fallsRiskScreenTableId = fallsRiskScreenTableSchema['id']
    # print(f'{SpeakCareEmrApi.FALL_RISK_SCREEN_TABLE} Table {fallsRiskScreenTableId} schema: {json.dumps(fallsRiskScreenTableSchema, indent=4)}')
    # fallsRiskTableWritableFields = api.get_table_writable_fields(tableId=fallsRiskScreenTableId)
    # print(f'{SpeakCareEmrApi.FALL_RISK_SCREEN_TABLE} Table writable fields: {json.dumps(fallsRiskTableWritableFields, indent=4)}')

    patientsWritableFields = api.get_table_writable_fields(tableName=SpeakCareEmrApi.PATIENTS_TABLE)
    print(f'{SpeakCareEmrApi.PATIENTS_TABLE} Table writable fields: {json.dumps(patientsWritableFields, indent=4)}')

    blablaWrtiableFields = api.get_table_writable_fields(tableName='blabla')
    print(f'blabla Table writable fields: {json.dumps(blablaWrtiableFields, indent=4)}')

    patientTableId = api.get_table_schema(tableName=SpeakCareEmrApi.PATIENTS_TABLE)['id']
    print(f'Patient table id: {patientTableId}')
    patientsWritableFields = api.get_table_writable_fields(tableId=patientTableId)
    print(f'{SpeakCareEmrApi.PATIENTS_TABLE} Table writable fields: {json.dumps(patientsWritableFields, indent=4)}')


    #print(f'Tables type is {type(tables)})')
    #print(f'Tables (type={type(tables)}): {json.dumps(tables, indent=4)}')
    # weightRecord = WeightRecord(patientId='recWya4qhPh1KZIor', nurseId='recVmeNQcsWUkbB41',  weight=170)
    # print(f'Weight record: {weightRecord}')
    # print(f'Weight record JSON: {weightRecord.to_json()}')
    # weights = [weightRecord.to_dict()]
    # print(f'Weights: {weights}')
    #api.create_records(WeightRecord.WEIGHTS_TABLE_ID, weights)
    #record = api.create_record(WeightRecord.WEIGHTS_TABLE_ID, weightRecord.to_dict())
    #print(f'Created weight record: {record}')

    # weightRecords = [WeightRecord(patientId='recuGGwjlzPbDNFBW', nurseId='rechjFqtbZ35X8ayu',  weight=170).to_dict(), 
    #                  WeightRecord(patientId='recuGGwjlzPbDNFBW', nurseId='rechjFqtbZ35X8ayu',  weight=165).to_dict(),
    #                  WeightRecord(patientId='recuGGwjlzPbDNFBW', nurseId='rechjFqtbZ35X8ayu',  weight=175).to_dict()]
    
    # records = api.create_records_batch(WeightRecord.WEIGHTS_TABLE_ID, weightRecords)
    # print(f'Created weight records for patientId=recuGGwjlzPbDNFBW recrods: {records}')


    
if __name__ == "__main__":
    main(sys.argv[1:])