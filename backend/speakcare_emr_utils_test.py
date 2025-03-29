#import speakcare_emr_utils
from models import MedicalRecords, Transcripts, RecordType, RecordState, TranscriptState
from speakcare_emr_utils import EmrUtils
from speakcare_emr import SpeakCareEmr
from speakcare_logging import SpeakcareLogger
from typing import Optional
import json
import os
from speakcare_env import SpeakcareEnv


run_skipped_tests = False
SpeakcareEnv.load_env()
run_skipped_tests = os.getenv('UT_RUN_SKIPPED_TESTS', 'False').lower() == 'true'
print(f"run_skipped_tests: {run_skipped_tests}")

# define setUp and tearDown functions for the test module
def setUpModule():
    # This runs once before all test classes in this module
    print(f"Setup module {__name__}")
    EmrUtils.init_db('test_db', create_db=True)

def tearDownModule():
    # This runs once after all test classes in this module
    print(f"Teardown module {__name__}")
    EmrUtils.cleanup_db(delete_db_files=True)

import unittest


class TestRecords(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestRecords, self).__init__(*args, **kwargs)
        self.logger = SpeakcareLogger(__name__)

    def setUp(self):
        pass

    def test_record_create(self):
                # Create a record example
        record_data = {
            "type": RecordType.SIMPLE,
            "table_name": SpeakCareEmr.WEIGHTS_TABLE,
            "patient_name": "James Brown",
            "nurse_name": "Sara Foster",
            "fields": {
                 "Units": "Lbs",
                 "Weight": 120,
                 "Scale": "Bath"
            }
        }
        record_id, state, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)
        self.assertEqual(response['message'], "EMR record created successfully")

        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.PENDING)
        self.assertEqual(record.state, state)
        self.logger.info(f"Created record {record_id}")

    def test_record_create_with_extra_field(self):
                # Create a record example
        record_data = {
            "type": RecordType.SIMPLE,
            "table_name": SpeakCareEmr.WEIGHTS_TABLE,
            "patient_name": "James Brown",
            "nurse_name": "Sara Foster",
            "fields": {
                 "Units": "Lbs",
                 "Weight": 120,
                 "Time": "12:00", # extra field
                 "Scale": "Bath"
            }
        }
        record_id, state, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)
        self.assertEqual(response['message'], "EMR record created successfully")

        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.PENDING)
        self.assertEqual(record.state, state)
        self.assertEqual(len(record.errors), 1)
        self.assertEqual(record.errors[0], "Field name 'Time' does not exist in the schema of table Weights.")
        self.logger.info(f"Created record {record_id}")

    def test_record_create_and_update(self):
                # Create a record example
        record_data = {
            "type": RecordType.SIMPLE,
            "table_name": SpeakCareEmr.WEIGHTS_TABLE,
            "patient_name": "James Brown",
            "nurse_name": "Sara Foster",
            "fields": {
                 "Units": "Pounds", # use wrong field here
                 "Weight": 120,
                 "Scale": "Bath"
            }
        }
        record_id, state, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)        
        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.state, RecordState.ERRORS)
        self.assertEqual(record.state, state)
        self.logger.info(f"Record {record_id} created with errors:{record.errors}")

        # fix the record
        record_data = {
            "patient_name": "James Brown",
            "nurse_name": "Sara Foster",
            "fields": {
                 "Units": "Lbs",
                 "Scale": "Bath"
                 # not proviuind Weight intentionally to test the partial update
            }
        }
        success, response  = EmrUtils.update_record(record_data, record_id)
        self.assertTrue(success, response)
        record, err = EmrUtils.get_record(record_id)
        self.assertEqual(record.id, record_id)
        # check that state is now PENDING
        self.assertEqual(record.state, RecordState.PENDING)
        self.logger.info(f"Created record {record_id}")

    def test_record_create_and_update_with_errors(self):
        # Create a record with 3 errors
        record_data = {
            "type": RecordType.SIMPLE,
            "table_name": SpeakCareEmr.WEIGHTS_TABLE,
            "patient_name": "Bruce Willis", # wrong patient name
            "nurse_name": "Sara Parker", # wrong nurse name
            "fields": {
                 "Units": "Pounds", # use wrong value here
                 "Weight": 120,
                 "Scale": "Bath"
            }
        }
        record_id, state, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)        
        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.state, RecordState.ERRORS)
        self.assertEqual(record.state, state)
        self.logger.info(f"Record {record_id} created with errors:{record.errors}")
        self.assertTrue(len(record.errors) >= 3) # at least 3 errors
        self.assertEqual(record.errors[0], "Patient 'Bruce Willis' not found in the EMR.")
        self.assertEqual(record.errors[1], "Nurse 'Sara Parker' not found in the EMR.")
        self.assertTrue("Units" in record.errors[2] and "Pounds" in record.errors[2], record.errors[2])

        # fix only the patient name
        record_data = {
            "patient_name": "James Brown",
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
            "patient_name": "James Brown", # wrong patient name
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
            "patient_name": "James Brown", # wrong patient name
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
            "type": RecordType.SIMPLE,
            "table_name": SpeakCareEmr.WEIGHTS_TABLE,
            "patient_name": "James Brown",
            "nurse_name": "Sara Foster",
            "patient_id": 1234567890,
            "fields": {
                 "Units": "Lbs",
                 "Weight": 120,
                 "Scale": "Bath"
            }
        }
        record_id, state, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)        
        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.state, RecordState.ERRORS)
        self.assertEqual(record.state, state)
        self.assertEqual(len(record.errors), 1)
        self.assertEqual(record.errors[0], "Patient ID '1234567890' not found in the EMR.")

        self.logger.info(f"Created record {record_id} with errors:{record.errors}")

        # try to fix but provide wrong patient name
        record_data = {
            "patient_name": "James Belushi", # wrong patient name
            "patient_id": 1
        }
        success, response = EmrUtils.update_record(record_data, record_id)
        self.assertFalse(success, response)
        record, err = EmrUtils.get_record(record_id)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.ERRORS)
        self.assertEqual(len(record.errors), 1)
        # we don't change the fields if we can't get it validated
        self.assertEqual(record.errors[0], "Patient ID '1234567890' not found in the EMR.")
        

        # now fix the patient id and use correct patient name
        record_data = {
            "patient_name": "James Broun", # slgihtly different name - should pass ok
            "patient_id": 1
        }
        success, response = EmrUtils.update_record(record_data, record_id)
        self.assertTrue(success, response)
        record, err = EmrUtils.get_record(record_id)
        self.assertEqual(record.id, record_id)
        # check that state is now PENDING
        self.assertEqual(record.state, RecordState.PENDING)
        self.assertEqual(len(record.errors), 0)
        self.logger.info(f"Updated record {record_id} successfully")


    def test_record_wrong_patient_id(self):
        # Create a record with non-existent patient id
        record_data = {
            "type": RecordType.SIMPLE,
            "table_name": SpeakCareEmr.WEIGHTS_TABLE,
            "patient_name": "James Brown",
            "nurse_name": "Sara Foster",
            "patient_id": 2,
            "fields": {
                 "Units": "Lbs",
                 "Weight": 120,
                 "Scale": "Bath"
            }
        }
        record_id, state, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)        
        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.state, RecordState.ERRORS)
        self.assertEqual(record.state, state)
        self.assertEqual(len(record.errors), 1)
        self.assertEqual(record.errors[0], "Patient ID '2' does not match the patient ID '1' found by name 'James Brown'.")

        self.logger.info(f"Created record {record_id} with errors:{record.errors}")

        # fix it
        record_data = {
            "patient_name": "James Brown",
            "patient_id": 1
        }
        success, response = EmrUtils.update_record(record_data, record_id)
        self.assertTrue(success)
        record, err = EmrUtils.get_record(record_id)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.PENDING)
        self.assertEqual(len(record.errors), 0)
        self.logger.info(f"Updated record {record_id} successfully")


    def test_record_create_and_commit_record(self):
                # Create a record example
        record_data = {
            "type": RecordType.SIMPLE,
            "table_name": SpeakCareEmr.WEIGHTS_TABLE,
            "patient_name": "James Brown",
            "nurse_name": "Sara Foster",
            "fields": {
                 "Units": "Kg",
                 "Weight": 130,
                 "Scale": "Mechanical Lift"
            }
        }
        record_id, record_state, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)
        self.assertEqual(response['message'], "EMR record created successfully")

        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.PENDING)
        self.logger.info(f"Created record {record_id}")

        emr_id, record_state, response = EmrUtils.commit_record_to_emr(record_id)
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
        self.assertEqual(emr_record['fields']['PatientName (from Patient)'], ["James Brown"])
        self.assertEqual(emr_record['fields']['CreatedByName (from CreatedBy)'], ["Sara Foster"])
        self.logger.info(f"Commited record {record_id} to the EMR successfully")

    def test_record_create_and_commit_blood_pressure(self):
                    # Create a record example
            record_data = {
                "type": RecordType.SIMPLE,
                "table_name": SpeakCareEmr.BLOOD_PRESSURES_TABLE,
                "patient_name": "James Brown",
                "nurse_name": "Sara Foster",
                "fields": {"Systolic": 130, "Diastolic": 85, "Position": "Sitting", "Arm": "Left", "Notes": "no answer"}
            }
            record_id, record_state, response = EmrUtils.create_record(record_data)
            self.assertIsNotNone(record_id)
            self.assertEqual(response['message'], "EMR record created successfully")

            record: Optional[MedicalRecords] = {}
            record, err = EmrUtils.get_record(record_id)
            self.assertIsNotNone(record)
            self.assertEqual(record.id, record_id)
            self.assertEqual(record.state, RecordState.PENDING)
            self.logger.info(f"Created record {record_id}")

            emr_id, record_state, response = EmrUtils.commit_record_to_emr(record_id)
            record, err = EmrUtils.get_record(record_id)
            self.assertIsNotNone(emr_id)
            self.assertEqual(response['message'], f"Record {record_id} commited successfully to the EMR.")
            self.assertEqual(record.state, RecordState.COMMITTED)
            emr_record, err = EmrUtils.get_emr_record(record_id)
            self.assertIsNotNone(emr_record)
            self.assertEqual(emr_record['id'], emr_id)
            self.assertEqual(emr_record['fields']['Systolic'], 130)
            self.assertEqual(emr_record['fields']['Diastolic'], 85)
            self.assertEqual(emr_record['fields']['Position'], "Sitting")
            self.assertEqual(emr_record['fields']['Arm'], "Left")  
            self.assertEqual(emr_record['fields']['PatientName (from Patient)'], ["James Brown"])
            self.assertEqual(emr_record['fields']['CreatedByName (from CreatedBy)'], ["Sara Foster"])
            self.logger.info(f"Commited record {record_id} to the EMR successfully")

    def test_record_create_and_commit_and_fail_on_second_commit(self):
                # Create a record example
        record_data = {
            "type": RecordType.SIMPLE,
            "table_name": SpeakCareEmr.WEIGHTS_TABLE,
            "patient_name": "James Brown",
            "nurse_name": "Sara Foster",
            "fields": {
                 "Units": "Kg",
                 "Weight": 130,
                 "Scale": "Mechanical Lift"
            }
        }
        record_id, record_state, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)
        self.assertEqual(response['message'], "EMR record created successfully")

        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.PENDING)
        self.logger.info(f"Created record {record_id}")

        emr_id, record_state, response = EmrUtils.commit_record_to_emr(record_id)
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(emr_id)
        self.assertEqual(response['message'], f"Record {record_id} commited successfully to the EMR.")
        self.assertEqual(record.state, RecordState.COMMITTED)

        # try to commit again
        emr_id, record_state, response = EmrUtils.commit_record_to_emr(record_id)
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNone(emr_id)
        self.assertEqual(response['error'], f"Record id {record_id} cannot be commited as it is in '{record.state}' state.")
        self.assertEqual(record.state, RecordState.COMMITTED)

    def test_record_create_and_commit_and_fail_on_update(self):
                # Create a record example
        record_data = {
            "type": RecordType.SIMPLE,
            "table_name": SpeakCareEmr.WEIGHTS_TABLE,
            "patient_name": "James Brown",
            "nurse_name": "Sara Foster",
            "fields": {
                 "Units": "Kg",
                 "Weight": 130,
                 "Scale": "Mechanical Lift"
            }
        }
        record_id, record_state, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)
        self.assertEqual(response['message'], "EMR record created successfully")

        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.PENDING)
        self.logger.info(f"Created record {record_id}")

        emr_id, record_state, response = EmrUtils.commit_record_to_emr(record_id)
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
            "type": RecordType.SIMPLE,
            "table_name": SpeakCareEmr.WEIGHTS_TABLE,
            "patient_name": "James Brown",
            "nurse_name": "Sara Foster",
            "fields": {
                 "Units": "Kg",
                 "Weight": 130,
                 "Scale": "Mechanical Lift"
            }
        }
        record_id, record_state, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)
        self.assertEqual(response['message'], "EMR record created successfully")

        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.PENDING)
        self.logger.info(f"Created record {record_id}")

        emr_id, record_state, response = EmrUtils.commit_record_to_emr(record_id)
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(emr_id)
        self.assertEqual(response['message'], f"Record {record_id} commited successfully to the EMR.")
        self.assertEqual(record.state, RecordState.COMMITTED)

        # try to update, should fail
        success, response = EmrUtils.discard_record(record_id)
        self.assertFalse(success)
        self.assertEqual(response['error'], f"Record id {record_id} cannot be discarded as it already COMMITTED.")
        self.assertEqual(record.state, RecordState.COMMITTED)

    def test_record_create_with_transcript(self):

        transcript_text = "Hello James Brown, I am going to meausre your weight now. I am going to use the Mechanical lift. You are weighing 130 Kilograms. Thnak you."
        transcript_id, response = EmrUtils.add_transcript(transcript_text)
        
        # Assert that the transcript was created successfully
        self.assertIsNotNone(transcript_id, "Failed to create transcript.")
        
        # Get the transcript from the database
        transcript, response = EmrUtils.get_transcript(transcript_id)
        self.assertIsNotNone(transcript, "Failed to retrieve transcript.")
        self.assertEqual(transcript.text, transcript_text, "Transcript text does not match.")
        self.assertEqual(transcript.state, TranscriptState.NEW, "Transcript state should be NEW.")
        # Create a record example
        record_data = {
            "type": RecordType.SIMPLE,
            "table_name": SpeakCareEmr.WEIGHTS_TABLE,
            "patient_name": "James Brown",
            "nurse_name": "Sara Foster",
            "fields": {
                 "Units": "Kg",
                 "Weight": 130,
                 "Scale": "Mechanical Lift"
            }
        }
        record_id, record_state, response = EmrUtils.create_record(record_data, transcript_id)
        self.assertIsNotNone(record_id)
        self.assertEqual(response['message'], "EMR record created successfully")

        # now check that the record is properly connected to the transcript
        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id, load_transcript=True) # load the transcript with the record
        self.assertIsNotNone(record)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.PENDING)
        self.assertEqual(record.transcript_id, transcript_id)

        record_transcript: Optional[Transcripts] = {}
        record_transcript = record.transcript
        self.assertIsNotNone(record_transcript, response)
        self.assertEqual(record_transcript.state, TranscriptState.PROCESSED, "Transcript state should be PROCESSED.")
        self.assertEqual(record_transcript.text, transcript_text, "Transcript text does not match.")

        # now check that the transcript is properly connected to the record
        transcript_with_record, response = EmrUtils.get_transcript(transcript_id, load_medical_records=True) # load the record with the transcript
        transcript_records = transcript_with_record.medical_records
        self.assertIsNotNone(transcript_records)
        self.assertEqual(transcript_records[0].id, record_id)
        self.logger.info(f"Created record {record_id} with transcript id {transcript_id} successfully")     






class TestRecordWithSections(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestRecordWithSections, self).__init__(*args, **kwargs)
        self.logger = SpeakcareLogger(__name__)

    def setUp(self):
        pass
    def test_record_create_fallrisk(self):
        record_data = {
            "type": RecordType.MULTI_SECTION,
            "table_name": SpeakCareEmr.FALL_RISK_SCREEN_TABLE,
            "patient_name": "James Brown",
            "nurse_name": "Sara Foster",
            "patient_id": 1,
            "fields": {
                 "Status": "New"
             }
        }

        record_sections = { 
            SpeakCareEmr.FALL_RISK_SCREEN_SECTION_1_TABLE:
            {
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
        }
        record_data['sections'] = record_sections
        record_id, record_state, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)
        self.assertEqual(response['message'], "EMR record created successfully")

        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.PENDING, f'Errors: {record.errors}')
        self.assertEqual(record.state, record_state)
        self.assertEqual(len(record.sections), 1)  
        self.logger.info(f"Created record {record_id}")
  
    def test_record_create_fallrisk_with_wrong_section_name(self):
        record_data = {
            "type": RecordType.MULTI_SECTION,
            "table_name": SpeakCareEmr.FALL_RISK_SCREEN_TABLE,
            "patient_name": "James Brown",
            "nurse_name": "Sara Foster",
            "patient_id": 1,
            "fields": {
                 "Status": "New"
             }
        }
        record_sections = { 
            "Wrong section name":
            {
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
        }
        record_data['sections'] = record_sections
        record_id, record_state, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)
        self.assertTrue(f"Section 'Wrong section name' not found in table '{SpeakCareEmr.FALL_RISK_SCREEN_TABLE}'" in response['error'], response['error'])


        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.ERRORS, f'Errors: {record.errors}')
        self.assertEqual(record.errors[0], f"Section 'Wrong section name' not found in table '{SpeakCareEmr.FALL_RISK_SCREEN_TABLE}'")
        self.logger.info(f"Created record {record_id}")

    def test_record_create_with_wrong_sections(self):

        record_data = { # this is a medical record should not have sections
            "type": RecordType.SIMPLE,
            "table_name": SpeakCareEmr.WEIGHTS_TABLE,
            "patient_name": "James Brown",
            "nurse_name": "Sara Foster",
            "fields": {
                 "Units": "Lbs",
                 "Weight": 120,
                 "Scale": "Bath"
            }
        }
        record_sections = { 
            SpeakCareEmr.FALL_RISK_SCREEN_SECTION_1_TABLE:
            {
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
        }
        record_data['sections'] = record_sections
        record_id, record_state, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)
        self.assertTrue(f"Sections '['{SpeakCareEmr.FALL_RISK_SCREEN_SECTION_1_TABLE}']' provided for table '{SpeakCareEmr.WEIGHTS_TABLE}' that has no sections" in response['error'], response['error'])


        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.ERRORS, f'Errors: {record.errors}')
        self.assertTrue("Sections '['Fall Risk Screen: SECTION 1']' provided for table 'Weights' that has no sections" in record.errors[0])
        self.logger.info(f"Created record {record_id} with errors:{record.errors}")
        

    def test_record_create_assessment_with_wrong_section_field(self):
        record_data = {
            "type": RecordType.MULTI_SECTION,
            "table_name": SpeakCareEmr.FALL_RISK_SCREEN_TABLE,
            "patient_name": "James Brown",
            "nurse_name": "Sara Foster",
            "patient_id": 1,
            "fields": {
                 "Status": "New"
             }
        }

        record_sections = { 
            SpeakCareEmr.FALL_RISK_SCREEN_SECTION_1_TABLE:
            {
                 "fields": {
                    "URINE ELIMINATION STATUS": "REGULARLY CONTINENT (0 points)",
                    "VISION STATUS": "ADEQUATE (with or without glasses) (0 points)",
                    "Total score": "ten", # "ten" instead of an integer
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
        }

        record_data['sections'] = record_sections
        record_id, record_state, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)
        self.assertEqual(response['message'], "EMR record created successfully", response)

        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.PENDING, f'Errors: {record.errors}')
        self.assertTrue("Section 'Fall Risk Screen: SECTION 1' validation failed with errors" in record.errors[0], record.errors)
        self.assertTrue("Validation error for a required field 'Total score' in table Fall Risk Screen: SECTION 1: Value 'ten' cannot be converted to a number."\
                         in record.sections['Fall Risk Screen: SECTION 1']['errors'], 
                         json.dumps(record.sections['Fall Risk Screen: SECTION 1'], indent=4))
        self.logger.info(f"Created record {record_id} with errors:{record.errors}")
    
    def test_record_create_assessment_commit_and_sign(self):
        record_data = {
            "type": RecordType.MULTI_SECTION,
            "table_name": SpeakCareEmr.FALL_RISK_SCREEN_TABLE,
            "patient_name": "James Brown",
            "nurse_name": "Sara Foster",
            "patient_id": 1,
            "fields": {
                 "Status": "New"
             }
        }

        record_sections = { 
            SpeakCareEmr.FALL_RISK_SCREEN_SECTION_1_TABLE:
            {
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
        }
        record_data['sections'] = record_sections
        record_id, record_state, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)
        self.assertEqual(response['message'], "EMR record created successfully", response)

        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.PENDING, f'Errors: {record.errors}')
        self.assertEqual(len(record.sections), 1)  
        self.logger.info(f"Created record {record_id}")

        emr_id, record_state, response = EmrUtils.commit_record_to_emr(record_id)
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

        EmrUtils.sign_assessment(record_id)
        emr_record, err = EmrUtils.get_emr_record(record_id)
        self.assertEqual(emr_record['fields']['Status'], "Completed")
        self.assertEqual(emr_record['fields']['SignedByName (from SignedBy)'], ["Sara Foster"])
  
    def test_record_create_vitals_commit_and_sign(self):
        record_data = {
            "type": RecordType.MULTI_SECTION,
            "table_name": SpeakCareEmr.VITALS_TABLE,
            "patient_name": "Bob Williams",
            "nurse_name": "Sara Foster",
            "patient_id": 3,
            "fields": {
                 "Status": "New"
             }
        }
        record_sections = {
            SpeakCareEmr.WEIGHTS_TABLE:
            {
                "fields": {"Units": "Lbs", "Weight": 120, "Scale": "Bath"}
            },
            SpeakCareEmr.BLOOD_PRESSURES_TABLE:
            {
                "fields": {"Systolic": 130, "Diastolic": 85, "Position": "Sitting", "Arm": "Left", "Notes": "no answer"}
            },
            SpeakCareEmr.TEMPERATURES_TABLE:
            {
                "fields": {"Degrees": 99.9, "Route": "Oral", "Units": "Fahrenheit"}
            },
            SpeakCareEmr.HEIGHTS_TABLE:
            {
                "fields": {"Height": 168, "Units": "Centimeters", "Method": "Wing span"}
            }
        }


        record_data['sections'] = record_sections
        record_id, record_state, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)
        self.assertEqual(response['message'], "EMR record created successfully")

        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.PENDING, f'Errors: {record.errors}')
        self.assertEqual(len(record.sections), 4)  
        self.logger.info(f"Created record {record_id}")

        emr_id, record_state, response = EmrUtils.commit_record_to_emr(record_id)
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(emr_id)
        self.assertEqual(response['message'], f"Record {record_id} commited successfully to the EMR.")
        self.assertEqual(record.state, RecordState.COMMITTED)
        emr_record, err = EmrUtils.get_emr_record(record_id)
        self.assertIsNotNone(emr_record)
        self.assertEqual(emr_record['id'], emr_id)
        self.assertEqual(emr_record['fields']['Status'], "New")

        # Check the blood pressure section
        self.assertIsNotNone(emr_record['fields']['Blood Pressure'])
        sectionEmrId = emr_record['fields']['Blood Pressure'][0]
        sectionTableId = EmrUtils.get_table_id(SpeakCareEmr.BLOOD_PRESSURES_TABLE)
        section_emr_record, err = EmrUtils.get_emr_record_by_emr_record_id(tableId=sectionTableId, emr_record_id= sectionEmrId)
        self.assertIsNotNone(section_emr_record)
        self.assertEqual(section_emr_record['fields']['Systolic'], 130)  
        self.assertEqual(section_emr_record['fields']['Diastolic'], 85)
        self.assertEqual(section_emr_record['fields']['Position'], "Sitting")
        self.assertEqual(section_emr_record['fields']['Arm'], "Left")
        self.assertEqual(section_emr_record['fields']['Notes'], "no answer")
        self.assertEqual(section_emr_record['fields']['CreatedByName (from CreatedBy)'], ["Sara Foster"])

        # Check the temperature section
        # "fields": {"Degrees": 99.9, "Route": "Oral", "Units": "Fahrenheit"}
        self.assertIsNotNone(emr_record['fields']['Temperature'])
        sectionEmrId = emr_record['fields']['Temperature'][0]
        sectionTableId = EmrUtils.get_table_id(SpeakCareEmr.TEMPERATURES_TABLE)
        section_emr_record, err = EmrUtils.get_emr_record_by_emr_record_id(tableId=sectionTableId, emr_record_id= sectionEmrId)
        self.assertIsNotNone(section_emr_record)
        self.assertEqual(section_emr_record['fields']['Degrees'], 99.9)  
        self.assertEqual(section_emr_record['fields']['Units'], "Fahrenheit")
        self.assertEqual(section_emr_record['fields']['Route'], "Oral")
        self.assertEqual(section_emr_record['fields']['CreatedByName (from CreatedBy)'], ["Sara Foster"])

        # Check the weight section
        # "fields": {"Units": "Lbs", "Weight": 120, "Scale": "Bath"}
        self.assertIsNotNone(emr_record['fields']['Weight'])
        sectionEmrId = emr_record['fields']['Weight'][0]
        sectionTableId = EmrUtils.get_table_id(SpeakCareEmr.WEIGHTS_TABLE)
        section_emr_record, err = EmrUtils.get_emr_record_by_emr_record_id(tableId=sectionTableId, emr_record_id= sectionEmrId)
        self.assertIsNotNone(section_emr_record)
        self.assertEqual(section_emr_record['fields']['Weight'], 120)  
        self.assertEqual(section_emr_record['fields']['Units'], "Lbs")
        self.assertEqual(section_emr_record['fields']['Scale'], "Bath")
        self.assertEqual(section_emr_record['fields']['CreatedByName (from CreatedBy)'], ["Sara Foster"])

        # Check the height section
        self.assertIsNotNone(emr_record['fields']['Height'])
        sectionEmrId = emr_record['fields']['Height'][0]
        sectionTableId = EmrUtils.get_table_id(SpeakCareEmr.HEIGHTS_TABLE)
        section_emr_record, err = EmrUtils.get_emr_record_by_emr_record_id(tableId=sectionTableId, emr_record_id= sectionEmrId)
        self.assertIsNotNone(section_emr_record)
        self.assertEqual(section_emr_record['fields']['Height'], 168)  
        self.assertEqual(section_emr_record['fields']['Units'], "Centimeters")
        self.assertEqual(section_emr_record['fields']['Method'], "Wing span")
        self.assertEqual(section_emr_record['fields']['CreatedByName (from CreatedBy)'], ["Sara Foster"])


        self.logger.info(f"Commited vitals {record_id} to the EMR successfully")

        EmrUtils.sign_assessment(record_id)
        emr_record, err = EmrUtils.get_emr_record(record_id)
        self.assertEqual(emr_record['fields']['Status'], "Completed")
        self.assertEqual(emr_record['fields']['SignedByName (from SignedBy)'], ["Sara Foster"])
  



### Transcript unit tests
class TestTranscripts(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestTranscripts, self).__init__(*args, **kwargs)
        self.logger = SpeakcareLogger(__name__)

    def setUp(self):
        pass

    def test_transcript_create(self):
        # Create a transcript
        transcript_text = "This is a new test transcript."
        transcript_id, response = EmrUtils.add_transcript(transcript_text)
        
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
        transcript_id, response = EmrUtils.add_transcript(transcript_text)
        
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
        transcript_id, response = EmrUtils.add_transcript(transcript_text)
        
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
        self.logger = SpeakcareLogger(__name__)

    def setUp(self):
        pass

    @unittest.skipIf(not run_skipped_tests, "Skipping by default")
    def test_get_all_record_writable_schema(self):
        # Getting all table schema example
        table_names = EmrUtils.get_table_names()
        for table_name in table_names:
            self.logger.info(f'Getting schema for table {table_name}')
            record_schema = EmrUtils.get_table_json_schema(table_name)
            self.assertIsNotNone(record_schema)
            self.logger.debug(f'{table_name} Table schema: {json.dumps(record_schema, indent=4)}') 

    def test_get_fallrisk_schema(self):
        # Getting schema for a specific table
        table_name = SpeakCareEmr.FALL_RISK_SCREEN_TABLE
        record_schema = EmrUtils.get_table_json_schema(table_name)
        self.assertIsNotNone(record_schema)
        self.logger.info(f'{table_name} Table schema: {json.dumps(record_schema, indent=4)}')

    def test_get_sports_3_schema(self):
        # Getting schema for a specific table
        table_name = SpeakCareEmr.SPORT_3_TEST
        record_schema = EmrUtils.get_table_json_schema(table_name)
        self.assertIsNotNone(record_schema)
        self.logger.debug(f'{table_name} Table schema: {json.dumps(record_schema, indent=4)}')

    def test_get_sports_2_schema(self):
        # Getting schema for a specific table
        table_name = SpeakCareEmr.SPORT_PERFORMANCE_ASSESSMENT_2
        record_schema = EmrUtils.get_table_json_schema(table_name)
        self.assertIsNotNone(record_schema)
        self.logger.debug(f'{table_name} Table schema: {json.dumps(record_schema, indent=4)}')

    def test_get_sports_4_schema(self):
        # Getting schema for a specific table
        table_name = SpeakCareEmr.SPORT_PERFORMANCE_ASSESSMENT_4
        record_schema = EmrUtils.get_table_json_schema(table_name)
        self.assertIsNotNone(record_schema)
        self.logger.debug(f'{table_name} Table schema: {json.dumps(record_schema, indent=4)}')
    

class TestPersons(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestPersons, self).__init__(*args, **kwargs)
        self.logger = SpeakcareLogger(__name__)

    def setUp(self):
        pass

    def test_create_patient(self):
                # Create a record example
        patient_data = {
            "FullName": "Samwise Gamgee",
            "FirstName": "Samwise",
            "LastName": "Gamgee",
            "DateOfBirth": "1980-04-06",
            "Gender": "Male",
            "Admission Date": "2024-06-01"
        }
        emr_patient_record, message = EmrUtils.add_patient(patient_data)
        self.assertIsNotNone(emr_patient_record)
        self.logger.info(f"Created patient {emr_patient_record['id']}")
        self.assertEqual(emr_patient_record['fields']['FullName'], "Samwise Gamgee", message)
        self.assertEqual(emr_patient_record['fields']['FirstName'], "Samwise", message)
        self.assertEqual(emr_patient_record['fields']['LastName'], "Gamgee", message)
        self.assertEqual(emr_patient_record['fields']['DateOfBirth'], "1980-04-06", message)
        self.assertEqual(emr_patient_record['fields']['Gender'], "Male", message)
        self.assertEqual(emr_patient_record['fields']['Admission Date'], "2024-06-01", message)

        # delete the patient
        delete_record = EmrUtils.delete_patient(emr_patient_record['id'])
        self.assertTrue(delete_record)
        self.assertEqual(delete_record['id'], emr_patient_record['id'], delete_record)
        self.assertTrue(delete_record['deleted'], delete_record)
        self.logger.info(f"Deleted patient {emr_patient_record['id']}")

    def test_create_patient_missing_field(self):
                # Create a record example
        patient_data = {
            "FullName": "Frodo Baggins",
            "FirstName": "Frodo",
            "LastName": "Baggins",
            #"DateOfBirth": "1968-09-22", # missing DateOfBirth
            "Gender": "Male",
            "Admission Date": "2024-05-01"
        }
        emr_patient_record, message = EmrUtils.add_patient(patient_data)
        # should fail
        self.assertIsNone(emr_patient_record, message)
        self.logger.info(f"Patient creation failed. Error: {message["error"]}")

        # add the missing field
        patient_data["DateOfBirth"] = "1968-09-22"
        emr_patient_record, message  = EmrUtils.add_patient(patient_data)
        # should succeed    
        self.logger.info(f"Created patient {emr_patient_record['id']}")
        self.assertEqual(emr_patient_record['fields']['FullName'], "Frodo Baggins", message)
        self.assertEqual(emr_patient_record['fields']['FirstName'], "Frodo", message)
        self.assertEqual(emr_patient_record['fields']['LastName'], "Baggins", message)
        self.assertEqual(emr_patient_record['fields']['DateOfBirth'], "1968-09-22", message)
        self.assertEqual(emr_patient_record['fields']['Gender'], "Male", message)
        self.assertEqual(emr_patient_record['fields']['Admission Date'], "2024-05-01", message)

        #delete the patient
        delete_record = EmrUtils.delete_patient(emr_patient_record['id'])
        self.assertTrue(delete_record)
        self.assertEqual(delete_record['id'], emr_patient_record['id'], delete_record)
        self.assertTrue(delete_record['deleted'], delete_record)
        self.logger.info(f"Deleted patient {emr_patient_record['id']}")
    
    def test_create_and_update_patient(self):
                # Create a record example
        patient_data = {
            "FullName": "Minerva McGonagall",
            "FirstName": "Minerva",
            "LastName": "McGonagall",
            "DateOfBirth": "1935-10-03",
            "Gender": "Female",
            "Admission Date": "2020-03-31"
        }
        emr_patient_record, message = EmrUtils.add_patient(patient_data)
        self.assertIsNotNone(emr_patient_record)
        self.logger.info(f"Created patient {emr_patient_record['id']}")
        self.assertEqual(emr_patient_record['fields']['FullName'], "Minerva McGonagall", message)
        self.assertEqual(emr_patient_record['fields']['FirstName'], "Minerva", message)
        self.assertEqual(emr_patient_record['fields']['LastName'], "McGonagall", message)
        self.assertEqual(emr_patient_record['fields']['DateOfBirth'], "1935-10-03", message)
        self.assertEqual(emr_patient_record['fields']['Gender'], "Female", message)
        self.assertEqual(emr_patient_record['fields']['Admission Date'], "2020-03-31", message)

        # update the patient
        update_data = {
            "DateOfBirth": "1935-10-04", # change existing field
            "TreatmentPlan": "Transfiguration", # add new field
        }
        emr_patient_record, message = EmrUtils.update_patient(emr_patient_record['id'], update_data)
        self.assertIsNotNone(emr_patient_record)
        self.logger.info(f"Updated patient {emr_patient_record['id']}")
        self.assertEqual(emr_patient_record['fields']['FullName'], "Minerva McGonagall", message)
        self.assertEqual(emr_patient_record['fields']['FirstName'], "Minerva", message)
        self.assertEqual(emr_patient_record['fields']['LastName'], "McGonagall", message)
        self.assertEqual(emr_patient_record['fields']['DateOfBirth'], "1935-10-04", message)
        self.assertEqual(emr_patient_record['fields']['Gender'], "Female", message)
        self.assertEqual(emr_patient_record['fields']['TreatmentPlan'], "Transfiguration", message)


        # delete the patient
        delete_record = EmrUtils.delete_patient(emr_patient_record['id'])
        self.assertTrue(delete_record)
        self.assertEqual(delete_record['id'], emr_patient_record['id'], delete_record)
        self.assertTrue(delete_record['deleted'], delete_record)
        self.logger.info(f"Deleted patient {emr_patient_record['id']}")

    def test_create_nurse(self):
                # Create a record example
        nurse_data = {
            "Name": "Florence Nightingale",
            "Specialization": ["Cardiology", "Geriatrics", "Oncology"]
        }
        emr_nurse_record, message = EmrUtils.add_nurse(nurse_data)
        self.assertIsNotNone(emr_nurse_record)
        self.logger.info(f"Created nurse {emr_nurse_record['id']}")
        self.assertEqual(emr_nurse_record['fields']['Name'], "Florence Nightingale", message)
        self.assertEqual(emr_nurse_record['fields']['Specialization'], ["Cardiology", "Geriatrics", "Oncology"], message)

        # delete the nurse
        delete_record = EmrUtils.delete_nurse(emr_nurse_record['id'])
        self.assertTrue(delete_record)
        self.assertEqual(delete_record['id'], emr_nurse_record['id'], delete_record)
        self.assertTrue(delete_record['deleted'], delete_record)
        self.logger.info(f"Deleted nurse {emr_nurse_record['id']}")

    def test_create_nurse_missing_field(self):
                # Create a record example
        nurse_data = {
            "Name": "Florence Nightingale",
            #"Specialization": ["Cardiology", "Geriatrics", "Oncology"]
        }
        emr_nurse_record, message = EmrUtils.add_nurse(nurse_data)
        # should fail
        self.assertIsNone(emr_nurse_record, message)
        self.logger.info(f"Nurse creation failed. Error: {message["error"]}")

        # add the missing field
        nurse_data["Specialization"] = ["Cardiology", "Geriatrics", "Oncology"]
        emr_nurse_record, message  = EmrUtils.add_nurse(nurse_data)
        # should succeed    
        self.logger.info(f"Created nurse {emr_nurse_record['id']}")
        self.assertEqual(emr_nurse_record['fields']['Name'], "Florence Nightingale", message)
        self.assertEqual(emr_nurse_record['fields']['Specialization'], ["Cardiology", "Geriatrics", "Oncology"], message)

        #delete the nurse
        delete_record = EmrUtils.delete_nurse(emr_nurse_record['id'])
        self.assertTrue(delete_record)
        self.assertEqual(delete_record['id'], emr_nurse_record['id'], delete_record)
        self.assertTrue(delete_record['deleted'], delete_record)
        self.logger.info(f"Deleted nurse {emr_nurse_record['id']}")
    

    def test_create_and_update_nurse(self):
                
        nurse_data = {
            "Name": "Poppy Pomfrey",
            "Specialization": ["Pediatrics", "Orthopedics", "Dermatology"]
        }
        emr_nurse_record, message = EmrUtils.add_nurse(nurse_data)
        self.assertIsNotNone(emr_nurse_record)
        self.logger.info(f"Created patient {emr_nurse_record['id']}")
        self.assertEqual(emr_nurse_record['fields']['Name'], "Poppy Pomfrey", message)
        self.assertEqual(emr_nurse_record['fields']['Specialization'], ["Pediatrics", "Orthopedics", "Dermatology"], message)


        # update the nurse
        update_data = {
            "Name": "Poppy Pomfrey", # change existing field
            "Specialization": ["Pediatrics", "Orthopedics", "Dermatology", "Neurology"], # update field
            "Schedule": "Sunday day shift. Tuesday night shift" # add new field

        }
        emr_nurse_record, message = EmrUtils.update_nurse(emr_nurse_record['id'], update_data)
        self.assertIsNotNone(emr_nurse_record)
        self.logger.info(f"Updated patient {emr_nurse_record['id']}")
        self.assertEqual(emr_nurse_record['fields']['Name'], "Poppy Pomfrey", message)
        self.assertEqual(emr_nurse_record['fields']['Specialization'], ["Pediatrics", "Orthopedics", "Dermatology", "Neurology"], message)
        self.assertEqual(emr_nurse_record['fields']['Schedule'], "Sunday day shift. Tuesday night shift", message)


        # delete the nurse
        delete_record = EmrUtils.delete_nurse(emr_nurse_record['id'])
        self.assertTrue(delete_record)
        self.assertEqual(delete_record['id'], emr_nurse_record['id'], delete_record)
        self.assertTrue(delete_record['deleted'], delete_record)
        self.logger.info(f"Deleted nurse {emr_nurse_record['id']}")



if __name__ == '__main__':
    unittest.main()
