import speakcare_emr_utils
from speakcare_emr_utils import EmrUtils
from speakcare_emr import SpeakCareEmr
from models import MedicalRecords, Transcripts, RecordType, RecordState
from speakcare_logging import create_logger
from typing import Optional
import json
import unittest

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
        response, record_id = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)
        self.assertEqual(response['message'], "EMR record created successfully")

        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.PENDING)
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
        response, record_id = EmrUtils.create_record(record_data)
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
        response, record_id = EmrUtils.update_record(record_data, record_id)
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
        response, record_id = EmrUtils.create_record(record_data)
        self.assertIsNotNone(record_id)        
        record: Optional[MedicalRecords] = {}
        record, err = EmrUtils.get_record(record_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.state, RecordState.ERRORS)
        self.assertEqual(len(record.errors), 3) # patient not found and wrong Units field
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
        response, record_id = EmrUtils.update_record(record_data, record_id)
        record, err = EmrUtils.get_record(record_id)
        self.assertEqual(record.id, record_id)
         # check that state is still ERROR
        self.assertEqual(record.state, RecordState.ERRORS)
        self.assertEqual(len(record.errors), 3) # patient not found and wrong Units field
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
        response, record_id = EmrUtils.update_record(record_data, record_id)
        record, err = EmrUtils.get_record(record_id)
        self.assertEqual(record.id, record_id)
         # check that state is still ERROR
        self.assertEqual(record.state, RecordState.ERRORS)
        self.assertEqual(len(record.errors), 3) # patient not found and wrong Units field
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

        response, record_id = EmrUtils.update_record(record_data, record_id)
        record, err = EmrUtils.get_record(record_id)
        self.assertEqual(record.id, record_id)
        # check that state is still ERROR
        self.assertEqual(record.state, RecordState.ERRORS)
        self.assertEqual(len(record.errors), 3) # patient not found and wrong Units field
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

        response, record_id = EmrUtils.update_record(record_data, record_id)
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
        response, record_id = EmrUtils.create_record(record_data)
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
        response, record_id = EmrUtils.update_record(record_data, record_id)
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
        response, record_id = EmrUtils.update_record(record_data, record_id)
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
        response, record_id = EmrUtils.create_record(record_data)
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
        response, record_id = EmrUtils.update_record(record_data, record_id)
        record, err = EmrUtils.get_record(record_id)
        self.assertEqual(record.id, record_id)
        self.assertEqual(record.state, RecordState.PENDING)
        self.assertEqual(len(record.errors), 0)
        self.logger.info(f"Updated record {record_id} successfully")
        

    @unittest.skip("Skipping this test by default")
    def test_get_all_record_writable_schema(self):
        # Getting all table schema aexample
        table_names = EmrUtils.get_table_names()
        for table_name in table_names:
            self.logger.info(f'Getting schema for table {table_name}')
            record_schema, secitions_schema = EmrUtils.get_record_writable_schema(table_name)
            self.assertIsNotNone(record_schema)
            self.logger.debug(f'{table_name} Table schema: {json.dumps(record_schema, indent=4)}') 
            if secitions_schema:
                for section, schema in secitions_schema.items():
                    self.logger.info(f"Getting schema for section {section} in table {table_name}")
                    self.logger.debug(f"{table_name} Table {section} section schema: {json.dumps(schema, indent=4)}")
    



if __name__ == '__main__':
    unittest.main()
