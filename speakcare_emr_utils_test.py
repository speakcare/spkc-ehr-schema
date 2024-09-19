import speakcare_emr_utils
from speakcare_emr_utils import EmrUtils
from speakcare_emr import SpeakCareEmr
from models import MedicalRecords, Transcripts, RecordType, RecordState
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


class TestEmrUtils(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestEmrUtils, self).__init__(*args, **kwargs)
        self.logger = create_logger(__name__)

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
        record_id, response = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)
        self.assertEqual(response['message'], "EMR record created successfully")

        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.PENDING)
        self.logger.info(f"Created record {record_id}")

    def test_create_record_with_extra_field(self):
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
        record_id, response  = EmrUtils.update_record(record_data, record_id)
        record, err = EmrUtils.get_record(record_id)
        self.assertEqual(record.id, record_id)
        # check that state is now PENDING
        self.assertEqual(record.state, RecordState.PENDING)
        self.logger.info(f"Created record {record_id}")

    def test_create_and_update_with_errors(self):
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
        failed_record_id, response  = EmrUtils.update_record(record_data, record_id)
        self.assertIsNone(failed_record_id)
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
        failed_record_id, response = EmrUtils.update_record(record_data, record_id)
        self.assertIsNone(failed_record_id)
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

        failed_record_id, response = EmrUtils.update_record(record_data, record_id)
        self.assertIsNone(failed_record_id)
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

        record_id, response = EmrUtils.update_record(record_data, record_id)
        record, err = EmrUtils.get_record(record_id)
        self.assertEqual(record.id, record_id)
        # check that state is now PENDING
        self.assertEqual(record.state, RecordState.PENDING)
        self.assertEqual(len(record.errors), 0) 

        self.logger.info(f"Created record {record_id} successfully")


    def test_non_existent_patient_id(self):
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
        failed_record_id, response = EmrUtils.update_record(record_data, record_id)
        self.assertIsNone(failed_record_id)
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
        record_id, response = EmrUtils.update_record(record_data, record_id)
        record, err = EmrUtils.get_record(record_id)
        self.assertEqual(record.id, record_id)
        # check that state is now PENDING
        self.assertEqual(record.state, RecordState.PENDING)
        self.assertEqual(len(record.errors), 0)
        self.logger.info(f"Updated record {record_id} successfully")


    def test_wrong_patient_id(self):
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
        record_id, response = EmrUtils.update_record(record_data, record_id)
        record, err = EmrUtils.get_record(record_id)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.PENDING)
        self.assertEqual(len(record.errors), 0)
        self.logger.info(f"Updated record {record_id} successfully")
        

    def test_create_and_commit_record(self):
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


    def test_create_and_commit_and_fail_on_second_commit(self):
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

    def test_create_and_commit_and_fail_on_update(self):
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
        record_update_id, response = EmrUtils.update_record(record_data, record_id)
        self.assertIsNone(record_update_id)
        self.assertEqual(response['error'], f"Record is {record_id} is in {record.state} state and cannot be updated.")
        self.assertEqual(record.state, RecordState.COMMITTED)

    def test_create_and_commit_and_fail_on_discard(self):
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
        record_update_id, response = EmrUtils.discard_record(record_id)
        self.assertIsNone(record_update_id)
        self.assertEqual(response['error'], f"Record id {record_id} cannot be discarded as it already COMMITTED.")
        self.assertEqual(record.state, RecordState.COMMITTED)



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
