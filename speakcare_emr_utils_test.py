import speakcare_emr_utils
from speakcare_emr_utils import EmrUtils
from speakcare_emr import SpeakCareEmr
from models import MedicalRecords, Transcripts, RecordType, RecordState, TranscriptState
from speakcare_logging import create_logger
from typing import Optional
import json
import unittest
from dotenv import load_dotenv
import os


run_skipped_tests = False
load_dotenv()
run_skipped_tests = os.getenv('UT_RUN_SKIPPED_TESTS', 'False').lower() == 'true'
print(f"run_skipped_tests: {run_skipped_tests}")


class TestRecords(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestRecords, self).__init__(*args, **kwargs)
        self.logger = create_logger(__name__)

    def setUp(self):
        pass

    def test_record_create(self):
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
        record_id, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)
        self.assertEqual(response['message'], "EMR record created successfully")

        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.PENDING)
        self.logger.info(f"Created record {record_id}")

    def test_record_create_with_extra_field(self):
                # Create a record example
        record_data = {
            "type": RecordType.MEDICAL_RECORD,
            "table_name": SpeakCareEmr.WEIGHTS_TABLE,
            "patient_name": "John Doe",
            "nurse_name": "Sara Foster",
            "fields": {
                 "Units": "Lbs",
                 "Weight": 120,
                 "Time": "12:00", # extra field
                 "Scale": "Bath"
            }
        }
        record_id, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)
        self.assertEqual(response['message'], "EMR record created successfully")

        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.PENDING)
        self.assertEqual(len(record.errors), 1)
        self.assertEqual(record.errors[0], "Field name 'Time' does not exist in the schema.")
        self.logger.info(f"Created record {record_id}")

    def test_record_create_and_update(self):
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
        record_id, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)        
        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.state, RecordState.ERRORS)
        self.logger.info(f"Record {record_id} created with errors:{record.errors}")

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
        success, response  = EmrUtils.update_record(record_data, record_id)
        self.assertTrue(success)
        record, err = EmrUtils.get_record(record_id)
        self.assertEqual(record.id, record_id)
        # check that state is now PENDING
        self.assertEqual(record.state, RecordState.PENDING)
        self.logger.info(f"Created record {record_id}")

    def test_record_create_and_update_with_errors(self):
        # Create a record with 3 errors
        record_data = {
            "type": RecordType.MEDICAL_RECORD,
            "table_name": SpeakCareEmr.WEIGHTS_TABLE,
            "patient_name": "Bruce Willis", # wrong patient name
            "nurse_name": "Sara Parker", # wrong nurse name
            "fields": {
                 "Units": "Pounds", # use wrong value here
                 "Weight": 120,
                 "Scale": "Bath"
            }
        }
        record_id, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)        
        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.state, RecordState.ERRORS)
        self.logger.info(f"Record {record_id} created with errors:{record.errors}")
        self.assertTrue(len(record.errors) >= 3) # at least 3 errors
        self.assertEqual(record.errors[0], "Patient 'Bruce Willis' not found in the EMR.")
        self.assertEqual(record.errors[1], "Nurse 'Sara Parker' not found in the EMR.")
        self.assertTrue("Units" in record.errors[2] and "Pounds" in record.errors[2], record.errors[2])

        # fix only the patient name
        record_data = {
            "patient_name": "John Doe",
            "nurse_name": "Sara Parker",
            "fields": {
                 "Units": "Pounds", # use wrong field here
            }
        }
        success, response  = EmrUtils.update_record(record_data, record_id)
        self.assertFalse(success)
        record, err = EmrUtils.get_record(record_id)
        self.assertEqual(record.id, record_id)
         # check that state is still ERROR
        self.assertEqual(record.state, RecordState.ERRORS)
        self.assertTrue(len(record.errors) >= 3) # at least 3 errors
        self.assertEqual(record.errors[0], "Patient 'Bruce Willis' not found in the EMR.")
        self.assertEqual(record.errors[1], "Nurse 'Sara Parker' not found in the EMR.")
        self.assertTrue("Units" in record.errors[2] and "Pounds" in record.errors[2], record.errors[2])
    
        # fix the Units field but mess up the Scale field
        record_data = {
            "fields": {
                 "Units": "Lbs", # use wrong field here
                 "Scale": "Bathroom"
            }
        }
        success, response = EmrUtils.update_record(record_data, record_id)
        self.assertFalse(success)
        record, err = EmrUtils.get_record(record_id)
        self.assertEqual(record.id, record_id)
         # check that state is still ERROR
        self.assertEqual(record.state, RecordState.ERRORS)
        self.assertTrue(len(record.errors) >= 3) # at least 3 errors
        self.assertEqual(record.errors[0], "Patient 'Bruce Willis' not found in the EMR.")
        self.assertEqual(record.errors[1], "Nurse 'Sara Parker' not found in the EMR.")
        self.assertTrue("Units" in record.errors[2] and "Pounds" in record.errors[2], record.errors[2])

    
        # fix all fields but the nurse
        record_data = {
            "patient_name": "John Doe", # wrong patient name
            "nurse_name": "Sara Parker", # wrong nurse name
            "fields": {
                 "Units": "Lbs", # use wrong value here
                 "Weight": 120,
                 "Scale": "Bath"
            }
        }

        success, response = EmrUtils.update_record(record_data, record_id)
        self.assertFalse(success)
        record, err = EmrUtils.get_record(record_id)
        self.assertEqual(record.id, record_id)
        # check that state is still ERROR
        self.assertEqual(record.state, RecordState.ERRORS)
        self.assertTrue(len(record.errors) >= 3) # at least 3 errors
        self.assertEqual(record.errors[0], "Patient 'Bruce Willis' not found in the EMR.")
        self.assertEqual(record.errors[1], "Nurse 'Sara Parker' not found in the EMR.")
        self.assertTrue("Units" in record.errors[2] and "Pounds" in record.errors[2], record.errors[2])

        # fix all fields
        record_data = {
            "patient_name": "John Doe", # wrong patient name
            "nurse_name": "Sara Foster", # wrong nurse name
            "fields": {
                 "Units": "Lbs", # use wrong value here
                 "Weight": 120,
                 "Scale": "Bath"
            }
        }    

        success, response = EmrUtils.update_record(record_data, record_id)
        self.assertTrue(success)
        record, err = EmrUtils.get_record(record_id)
        self.assertEqual(record.id, record_id)
        # check that state is now PENDING
        self.assertEqual(record.state, RecordState.PENDING)
        self.assertEqual(len(record.errors), 0) 

        self.logger.info(f"Created record {record_id} successfully")


    def test_record_non_existent_patient_id(self):
        # Create a record with non-existent patient id
        record_data = {
            "type": RecordType.MEDICAL_RECORD,
            "table_name": SpeakCareEmr.WEIGHTS_TABLE,
            "patient_name": "John Doe",
            "nurse_name": "Sara Foster",
            "patient_id": "1234567890",
            "fields": {
                 "Units": "Lbs",
                 "Weight": 120,
                 "Scale": "Bath"
            }
        }
        record_id, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)        
        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.state, RecordState.ERRORS)
        self.assertEqual(len(record.errors), 1)
        self.assertEqual(record.errors[0], "Patient ID '1234567890' not found in the EMR.")

        self.logger.info(f"Created record {record_id} with errors:{record.errors}")

        # try to fix but provide wrong patient name
        record_data = {
            "patient_name": "Johny Doggy",
            "patient_id": "P001"
        }
        success, response = EmrUtils.update_record(record_data, record_id)
        self.assertFalse(success)
        record, err = EmrUtils.get_record(record_id)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.ERRORS)
        self.assertEqual(len(record.errors), 1)
        # we don't change the fields if we can't get it validated
        self.assertEqual(record.errors[0], "Patient ID '1234567890' not found in the EMR.")
        

        # now fix the patient id and use correct patient name
        record_data = {
            "patient_name": "John Do", # slgihtly different name - should pass ok
            "patient_id": "P001"
        }
        success, response = EmrUtils.update_record(record_data, record_id)
        self.assertTrue(success)
        record, err = EmrUtils.get_record(record_id)
        self.assertEqual(record.id, record_id)
        # check that state is now PENDING
        self.assertEqual(record.state, RecordState.PENDING)
        self.assertEqual(len(record.errors), 0)
        self.logger.info(f"Updated record {record_id} successfully")


    def test_record_wrong_patient_id(self):
        # Create a record with non-existent patient id
        record_data = {
            "type": RecordType.MEDICAL_RECORD,
            "table_name": SpeakCareEmr.WEIGHTS_TABLE,
            "patient_name": "John Doe",
            "nurse_name": "Sara Foster",
            "patient_id": "P002",
            "fields": {
                 "Units": "Lbs",
                 "Weight": 120,
                 "Scale": "Bath"
            }
        }
        record_id, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)        
        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.state, RecordState.ERRORS)
        self.assertEqual(len(record.errors), 1)
        self.assertEqual(record.errors[0], "Patient ID 'P002' does not match the patient ID 'P001' found by name 'John Doe'.")

        self.logger.info(f"Created record {record_id} with errors:{record.errors}")

        # fix it
        record_data = {
            "patient_name": "John Doe",
            "patient_id": "P001"
        }
        success, response = EmrUtils.update_record(record_data, record_id)
        self.assertTrue(success)
        record, err = EmrUtils.get_record(record_id)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.PENDING)
        self.assertEqual(len(record.errors), 0)
        self.logger.info(f"Updated record {record_id} successfully")


    def test_record_create_assessment(self):
        record_data = {
            "type": RecordType.ASSESSMENT,
            "table_name": SpeakCareEmr.FALL_RISK_SCREEN_TABLE,
            "patient_name": "John Doe",
            "nurse_name": "Sara Foster",
            "patient_id": "P001",
            "fields": {
                 "Status": "New"
             }
        }

        rescord_sections = [
            {
                "table_name": SpeakCareEmr.FALL_RISK_SCREEN_SECTION_1_TABLE,
                 "fields": {
                    "URINE ELIMINATION STATUS": "REGULARLY CONTINENT (0 points)",
                    "VISION STATUS": "ADEQUATE (with or without glasses) (0 points)",
                    "Total score": 10,
                    "LEVEL OF CONSCIOUSNESS/ MENTAL STATUS": "Alert (0 points)",
                    "GAIT/BALANCE/AMBULATION": [
                        "Balance problem while standing/walking (1 point)"
                    ],
                    "MEDICATIONS": "NONE of these medications taken currently or within last 7 days (0 points)",
                    "PREDISPOSING DISEASES": "NONE PRESENT (0 points)",
                    "MEDICATIONS CHANGES": "Yes (1 additional point)",
                    "HISTORY OF FALLS (Past 3 Months)": "NO FALLS in past 3 months (0 points)"
                }
            }
        ]
        record_data['sections'] = rescord_sections
        record_id, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)
        self.assertEqual(response['message'], "EMR record created successfully")

        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.PENDING, f'Errors: {record.errors}')
        self.assertEqual(len(record.sections), 1)  
        self.logger.info(f"Created record {record_id}")
  
    def test_record_create_assessment_with_wrong_section_name(self):
        record_data = {
            "type": RecordType.ASSESSMENT,
            "table_name": SpeakCareEmr.FALL_RISK_SCREEN_TABLE,
            "patient_name": "John Doe",
            "nurse_name": "Sara Foster",
            "patient_id": "P001",
            "fields": {
                 "Status": "New"
             }
        }

        rescord_sections = [
            {
                "table_name": "Wrong section name",
                 "fields": {
                    "URINE ELIMINATION STATUS": "REGULARLY CONTINENT (0 points)",
                    "VISION STATUS": "ADEQUATE (with or without glasses) (0 points)",
                    "Total score": 10,
                    "LEVEL OF CONSCIOUSNESS/ MENTAL STATUS": "Alert (0 points)",
                    "GAIT/BALANCE/AMBULATION": [
                        "Balance problem while standing/walking (1 point)"
                    ],
                    "MEDICATIONS": "NONE of these medications taken currently or within last 7 days (0 points)",
                    "PREDISPOSING DISEASES": "NONE PRESENT (0 points)",
                    "MEDICATIONS CHANGES": "Yes (1 additional point)",
                    "HISTORY OF FALLS (Past 3 Months)": "NO FALLS in past 3 months (0 points)"
                }
            }
        ]
        record_data['sections'] = rescord_sections
        record_id, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)
        self.assertEqual(response['message'], "EMR record created successfully")

        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.ERRORS, f'Errors: {record.errors}')
        self.assertEqual(record.errors[0], f"Section 'Wrong section name' not found in table '{SpeakCareEmr.FALL_RISK_SCREEN_TABLE}'")
        self.logger.info(f"Created record {record_id}")

    def test_record_create_with_wrong_sections(self):

        record_data = { # this is a medical record should not have sections
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

        rescord_sections = [
            {
                "table_name": SpeakCareEmr.FALL_RISK_SCREEN_SECTION_1_TABLE,
                 "fields": {
                    "URINE ELIMINATION STATUS": "REGULARLY CONTINENT (0 points)",
                    "VISION STATUS": "ADEQUATE (with or without glasses) (0 points)",
                    "Total score": "ten", # wrong value sould be integer
                    "LEVEL OF CONSCIOUSNESS/ MENTAL STATUS": "Alert (0 points)",
                    "GAIT/BALANCE/AMBULATION": [
                        "Balance problem while standing/walking (1 point)"
                    ],
                    "MEDICATIONS": "NONE of these medications taken currently or within last 7 days (0 points)",
                    "PREDISPOSING DISEASES": "NONE PRESENT (0 points)",
                    "MEDICATIONS CHANGES": "Yes (1 additional point)",
                    "HISTORY OF FALLS (Past 3 Months)": "NO FALLS in past 3 months (0 points)"
                }
            }
        ]
        record_data['sections'] = rescord_sections
        record_id, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)
        self.assertEqual(response['message'], "EMR record created successfully")

        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.ERRORS, f'Errors: {record.errors}')
        self.assertTrue("Sections '['Fall Risk Screen: SECTION 1']' provided for table 'Weights' that has no sections" in record.errors[0])
        self.logger.info(f"Created record {record_id} with errors:{record.errors}")
        

    def test_record_create_assessment_with_wrong_section_field(self):
        record_data = {
            "type": RecordType.ASSESSMENT,
            "table_name": SpeakCareEmr.FALL_RISK_SCREEN_TABLE,
            "patient_name": "John Doe",
            "nurse_name": "Sara Foster",
            "patient_id": "P001",
            "fields": {
                 "Status": "New"
             }
        }

        rescord_sections = [
            {
                "table_name": SpeakCareEmr.FALL_RISK_SCREEN_SECTION_1_TABLE,
                 "fields": {
                    "URINE ELIMINATION STATUS": "REGULARLY CONTINENT (0 points)",
                    "VISION STATUS": "ADEQUATE (with or without glasses) (0 points)",
                    "Total score": "ten", # wrong value sould be integer
                    "LEVEL OF CONSCIOUSNESS/ MENTAL STATUS": "Alert (0 points)",
                    "GAIT/BALANCE/AMBULATION": [
                        "Balance problem while standing/walking (1 point)"
                    ],
                    "MEDICATIONS": "NONE of these medications taken currently or within last 7 days (0 points)",
                    "PREDISPOSING DISEASES": "NONE PRESENT (0 points)",
                    "MEDICATIONS CHANGES": "Yes (1 additional point)",
                    "HISTORY OF FALLS (Past 3 Months)": "NO FALLS in past 3 months (0 points)"
                }
            }
        ]
        record_data['sections'] = rescord_sections
        record_id, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)
        self.assertEqual(response['message'], "EMR record created successfully")

        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.ERRORS, f'Errors: {record.errors}')
        self.assertTrue("field 'Total score': Value 'ten'" in record.errors[0])
        self.logger.info(f"Created record {record_id} with errors:{record.errors}")
    
    def test_record_create_assessment_commit_and_sign(self):
        record_data = {
            "type": RecordType.ASSESSMENT,
            "table_name": SpeakCareEmr.FALL_RISK_SCREEN_TABLE,
            "patient_name": "John Doe",
            "nurse_name": "Sara Foster",
            "patient_id": "P001",
            "fields": {
                 "Status": "New"
             }
        }

        rescord_sections = [
            {
                "table_name": SpeakCareEmr.FALL_RISK_SCREEN_SECTION_1_TABLE,
                 "fields": {
                    "URINE ELIMINATION STATUS": "REGULARLY CONTINENT (0 points)",
                    "VISION STATUS": "ADEQUATE (with or without glasses) (0 points)",
                    "Total score": 10,
                    "LEVEL OF CONSCIOUSNESS/ MENTAL STATUS": "Alert (0 points)",
                    "GAIT/BALANCE/AMBULATION": [
                        "Balance problem while standing/walking (1 point)"
                    ],
                    "MEDICATIONS": "NONE of these medications taken currently or within last 7 days (0 points)",
                    "PREDISPOSING DISEASES": "NONE PRESENT (0 points)",
                    "MEDICATIONS CHANGES": "Yes (1 additional point)",
                    "HISTORY OF FALLS (Past 3 Months)": "NO FALLS in past 3 months (0 points)"
                }
            }
        ]
        record_data['sections'] = rescord_sections
        record_id, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)
        self.assertEqual(response['message'], "EMR record created successfully")

        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.PENDING, f'Errors: {record.errors}')
        self.assertEqual(len(record.sections), 1)  
        self.logger.info(f"Created record {record_id}")

        emr_id, response = EmrUtils.commit_record_to_emr(record_id)
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(emr_id)
        self.assertEqual(response['message'], f"Record {record_id} commited successfully to the EMR.")
        self.assertEqual(record.state, RecordState.COMMITTED)
        emr_record, err = EmrUtils.get_emr_record(record_id)
        self.assertIsNotNone(emr_record)
        self.assertEqual(emr_record['id'], emr_id)
        self.assertEqual(emr_record['fields']['Status'], "New")
        self.assertIsNotNone(emr_record['fields']['SECTION_1_FALL_RISK'])
        sectionEmrId = emr_record['fields']['SECTION_1_FALL_RISK'][0]
        sectionTableId = EmrUtils.get_table_id(SpeakCareEmr.FALL_RISK_SCREEN_SECTION_1_TABLE)
        section_emr_record, err = EmrUtils.get_emr_record_by_emr_record_id(
                                                tableId=sectionTableId, 
                                                emr_record_id= sectionEmrId
                                            )
        self.assertIsNotNone(section_emr_record)
        self.assertEqual(section_emr_record['fields']['URINE ELIMINATION STATUS'], "REGULARLY CONTINENT (0 points)")  
        self.assertEqual(section_emr_record['fields']['Total score'], 10)
        self.assertEqual(section_emr_record['fields']['CreatedByName (from CreatedBy)'], ["Sara Foster"])
        self.logger.info(f"Commited assessment {record_id} to the EMR successfully")

        EmrUtils.sign_assessgment(record_id)
        emr_record, err = EmrUtils.get_emr_record(record_id)
        self.assertEqual(emr_record['fields']['Status'], "Completed")
        self.assertEqual(emr_record['fields']['SignedByName (from SignedBy)'], ["Sara Foster"])
  

    def test_record_create_and_commit_record(self):
                # Create a record example
        record_data = {
            "type": RecordType.MEDICAL_RECORD,
            "table_name": SpeakCareEmr.WEIGHTS_TABLE,
            "patient_name": "John Doe",
            "nurse_name": "Sara Foster",
            "fields": {
                 "Units": "Kg",
                 "Weight": 130,
                 "Scale": "Mechanical Lift"
            }
        }
        record_id, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)
        self.assertEqual(response['message'], "EMR record created successfully")

        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.PENDING)
        self.logger.info(f"Created record {record_id}")

        emr_id, response = EmrUtils.commit_record_to_emr(record_id)
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(emr_id)
        self.assertEqual(response['message'], f"Record {record_id} commited successfully to the EMR.")
        self.assertEqual(record.state, RecordState.COMMITTED)
        emr_record, err = EmrUtils.get_emr_record(record_id)
        self.assertIsNotNone(emr_record)
        self.assertEqual(emr_record['id'], emr_id)
        self.assertEqual(emr_record['fields']['Units'], "Kg")
        self.assertEqual(emr_record['fields']['Weight'], 130)
        self.assertEqual(emr_record['fields']['Scale'], "Mechanical Lift")  
        self.assertEqual(emr_record['fields']['PatientName (from Patient)'], ["John Doe"])
        self.assertEqual(emr_record['fields']['CreatedByName (from CreatedBy)'], ["Sara Foster"])
        self.logger.info(f"Commited record {record_id} to the EMR successfully")


    def test_record_create_and_commit_blood_pressure(self):
                    # Create a record example
            record_data = {
                "type": RecordType.MEDICAL_RECORD,
                "table_name": SpeakCareEmr.BLOOD_PRESSURES_TABLE,
                "patient_name": "John Doe",
                "nurse_name": "Sara Foster",
                "fields": {"Systolic": 130, "Diastolic": 85, "Position": "Sitting Left Arm", "Notes": "no answer"}
            }
            record_id, response = EmrUtils.create_record(record_data)
            self.assertIsNotNone(record_id)
            self.assertEqual(response['message'], "EMR record created successfully")

            record: Optional[MedicalRecords] = {}
            record, err = EmrUtils.get_record(record_id)
            self.assertIsNotNone(record)
            self.assertEqual(record.id, record_id)
            self.assertEqual(record.state, RecordState.PENDING)
            self.logger.info(f"Created record {record_id}")

            emr_id, response = EmrUtils.commit_record_to_emr(record_id)
            record, err = EmrUtils.get_record(record_id)
            self.assertIsNotNone(emr_id)
            self.assertEqual(response['message'], f"Record {record_id} commited successfully to the EMR.")
            self.assertEqual(record.state, RecordState.COMMITTED)
            emr_record, err = EmrUtils.get_emr_record(record_id)
            self.assertIsNotNone(emr_record)
            self.assertEqual(emr_record['id'], emr_id)
            self.assertEqual(emr_record['fields']['Systolic'], 130)
            self.assertEqual(emr_record['fields']['Diastolic'], 85)
            self.assertEqual(emr_record['fields']['Position'], "Sitting Left Arm")  
            self.assertEqual(emr_record['fields']['PatientName (from Patient)'], ["John Doe"])
            self.assertEqual(emr_record['fields']['CreatedByName (from CreatedBy)'], ["Sara Foster"])
            self.logger.info(f"Commited record {record_id} to the EMR successfully")

    def test_record_create_and_commit_and_fail_on_second_commit(self):
                # Create a record example
        record_data = {
            "type": RecordType.MEDICAL_RECORD,
            "table_name": SpeakCareEmr.WEIGHTS_TABLE,
            "patient_name": "John Doe",
            "nurse_name": "Sara Foster",
            "fields": {
                 "Units": "Kg",
                 "Weight": 130,
                 "Scale": "Mechanical Lift"
            }
        }
        record_id, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)
        self.assertEqual(response['message'], "EMR record created successfully")

        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.PENDING)
        self.logger.info(f"Created record {record_id}")

        emr_id, response = EmrUtils.commit_record_to_emr(record_id)
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(emr_id)
        self.assertEqual(response['message'], f"Record {record_id} commited successfully to the EMR.")
        self.assertEqual(record.state, RecordState.COMMITTED)

        # try to commit again
        emr_id, response = EmrUtils.commit_record_to_emr(record_id)
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNone(emr_id)
        self.assertEqual(response['error'], f"Record id {record_id} cannot be commited as it is in '{record.state}' state.")
        self.assertEqual(record.state, RecordState.COMMITTED)

    def test_record_create_and_commit_and_fail_on_update(self):
                # Create a record example
        record_data = {
            "type": RecordType.MEDICAL_RECORD,
            "table_name": SpeakCareEmr.WEIGHTS_TABLE,
            "patient_name": "John Doe",
            "nurse_name": "Sara Foster",
            "fields": {
                 "Units": "Kg",
                 "Weight": 130,
                 "Scale": "Mechanical Lift"
            }
        }
        record_id, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)
        self.assertEqual(response['message'], "EMR record created successfully")

        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.PENDING)
        self.logger.info(f"Created record {record_id}")

        emr_id, response = EmrUtils.commit_record_to_emr(record_id)
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(emr_id)
        self.assertEqual(response['message'], f"Record {record_id} commited successfully to the EMR.")
        self.assertEqual(record.state, RecordState.COMMITTED)

        # try to update, should fail
        success, response = EmrUtils.update_record(record_data, record_id)
        self.assertFalse(success)
        self.assertEqual(response['error'], f"Record is {record_id} is in {record.state} state and cannot be updated.")
        self.assertEqual(record.state, RecordState.COMMITTED)

    def test_record_create_and_commit_and_fail_on_discard(self):
                # Create a record example
        record_data = {
            "type": RecordType.MEDICAL_RECORD,
            "table_name": SpeakCareEmr.WEIGHTS_TABLE,
            "patient_name": "John Doe",
            "nurse_name": "Sara Foster",
            "fields": {
                 "Units": "Kg",
                 "Weight": 130,
                 "Scale": "Mechanical Lift"
            }
        }
        record_id, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)
        self.assertEqual(response['message'], "EMR record created successfully")

        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.PENDING)
        self.logger.info(f"Created record {record_id}")

        emr_id, response = EmrUtils.commit_record_to_emr(record_id)
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(emr_id)
        self.assertEqual(response['message'], f"Record {record_id} commited successfully to the EMR.")
        self.assertEqual(record.state, RecordState.COMMITTED)

        # try to update, should fail
        success, response = EmrUtils.discard_record(record_id)
        self.assertFalse(success)
        self.assertEqual(response['error'], f"Record id {record_id} cannot be discarded as it already COMMITTED.")
        self.assertEqual(record.state, RecordState.COMMITTED)


### Transcript unit tests
class TestTranscripts(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestTranscripts, self).__init__(*args, **kwargs)
        self.logger = create_logger(__name__)

    def setUp(self):
        pass

    def test_transcript_create(self):
        # Create a transcript
        transcript_text = "This is a test transcript."
        transcript_id, response = EmrUtils.create_transcript(transcript_text)
        
        # Assert that the transcript was created successfully
        self.assertIsNotNone(transcript_id, "Failed to create transcript.")
        
        # Get the transcript from the database
        transcript, response = EmrUtils.get_transcript(transcript_id)
        self.assertIsNotNone(transcript, "Failed to retrieve transcript.")
        self.assertEqual(transcript.text, transcript_text, "Transcript text does not match.")
        self.assertEqual(transcript.state, TranscriptState.NEW, "Transcript state should be NEW.")

    def test_transcript_update_state(self):
        # Create a transcript
        transcript_text = "This is a test transcript for state update."
        transcript_id, response = EmrUtils.create_transcript(transcript_text)
        
        # Assert that the transcript was created successfully
        self.assertIsNotNone(transcript_id, "Failed to create transcript.")
        
        # Update the state of the transcript
        new_state = TranscriptState.PROCESSED
        update_success, response = EmrUtils.update_transcript_state(transcript_id, new_state)
        
        # Assert that the state was updated successfully
        self.assertTrue(update_success, "Failed to update transcript state.")
        
        # Get the transcript from the database
        transcript, response = EmrUtils.get_transcript(transcript_id)
        
        # Assert that the state was updated correctly
        self.assertIsNotNone(transcript, "Failed to retrieve transcript.")
        self.assertEqual(transcript.state, new_state, "Transcript state does not match the updated state.")

    def test_transcript_delete(self):
        # Create a transcript
        transcript_text = "This is a test transcript for deletion."
        transcript_id, response = EmrUtils.create_transcript(transcript_text)
        
        # Assert that the transcript was created successfully
        self.assertIsNotNone(transcript_id, "Failed to create transcript.")
        
        # Get the transcript from the database
        transcript, response = EmrUtils.get_transcript(transcript_id)
        
        # Assert that the transcript was retrieved successfully
        self.assertIsNotNone(transcript, "Failed to retrieve transcript.")
        
        # Delete the transcript
        delete_success, response = EmrUtils.delete_transcript(transcript_id)
        
        # Assert that the transcript was deleted successfully
        self.assertTrue(delete_success, "Failed to delete transcript.")
        
        # Try to get the transcript again, should fail
        transcript, response = EmrUtils.get_transcript(transcript_id)
        
        # Assert that the transcript is no longer in the database
        self.assertIsNone(transcript, "Transcript should not exist after deletion.")


### Schema unit tests
class TestSchema(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestSchema, self).__init__(*args, **kwargs)
        self.logger = create_logger(__name__)

    def setUp(self):
        pass

    @unittest.skipIf(not run_skipped_tests, "Skipping by default")
    def test_get_all_record_writable_schema(self):
        # Getting all table schema aexample
        table_names = EmrUtils.get_table_names()
        for table_name in table_names:
            self.logger.info(f'Getting schema for table {table_name}')
            record_schema, sections_schema = EmrUtils.get_record_writable_schema(table_name)
            self.assertIsNotNone(record_schema)
            self.logger.debug(f'{table_name} Table schema: {json.dumps(record_schema, indent=4)}') 
            if sections_schema:
                for section, schema in sections_schema.items():
                    self.logger.info(f"Getting schema for section {section} in table {table_name}")
                    self.logger.debug(f"{table_name} Table {section} section schema: {json.dumps(schema, indent=4)}")
    



if __name__ == '__main__':
    unittest.main()
