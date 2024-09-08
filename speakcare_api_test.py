import sys
import os
from pyairtable import Api as AirtableApi
import json
from enum import Enum
import logging


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
    


class APIClient:

    def __init__(self):
        self.api = AirtableApi(os.environ['AIRTABLE_API_KEY'])

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
    logging.getLogger().setLevel(logging.INFO)
    log = logging.getLogger("requests.packages.urllib3")
    log.setLevel(logging.INFO)
    log.propagate = True

    api = APIClient()
    weightRecord = WeightRecord(patientId='recWya4qhPh1KZIor', nurseId='recVmeNQcsWUkbB41',  weight=170)
    print(f'Weight record: {weightRecord}')
    print(f'Weight record JSON: {weightRecord.to_json()}')
    weights = [weightRecord.to_dict()]
    print(f'Weights: {weights}')
    #api.create_records(WeightRecord.WEIGHTS_TABLE_ID, weights)
    #record = api.create_record(WeightRecord.WEIGHTS_TABLE_ID, weightRecord.to_dict())
    #print(f'Created weight record: {record}')

    weightRecords = [WeightRecord(patientId='recuGGwjlzPbDNFBW', nurseId='rechjFqtbZ35X8ayu',  weight=170).to_dict(), 
                     WeightRecord(patientId='recuGGwjlzPbDNFBW', nurseId='rechjFqtbZ35X8ayu',  weight=165).to_dict(),
                     WeightRecord(patientId='recuGGwjlzPbDNFBW', nurseId='rechjFqtbZ35X8ayu',  weight=175).to_dict()]
    
    records = api.create_records_batch(WeightRecord.WEIGHTS_TABLE_ID, weightRecords)
    print(f'Created weight records for patientId=recuGGwjlzPbDNFBW recrods: {records}')
    
if __name__ == "__main__":
    main(sys.argv[1:])