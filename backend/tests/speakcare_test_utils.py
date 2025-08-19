import json
import os
import requests
from backend.tests.table_schemas import TableSchemas
from backend.speakcare_emr_tables import SpeakCareEmrTables
from backend.speakcare_env import SpeakcareEnv
from speakcare_logging import SpeakcareLogger

# Logger setup
test_utils_logger = SpeakcareLogger('test.utils')


class SpeakcareTestUtils:
    """ Class definition for SpeakcareTestUtils"""

    @classmethod
    def create_and_clear_table(cls, table, id_field_name):
        AIRTABLE_APP_BASE_ID = os.getenv('AIRTABLE_APP_BASE_ID')
        AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')
        
        emrTables = SpeakCareEmrTables()
        table_prefix = emrTables.get_person_table_prefix()
        table_name = table_prefix + "_" + table['name']

        success, record_deletion_required = AirtableUtils.create_airtable_table(
            base_id=AIRTABLE_APP_BASE_ID, 
            airtable_token=AIRTABLE_API_KEY, 
            table_name=table_name, 
            fields=table['fields'],
            id_field_name=id_field_name
            )
        
        if success:
            if len(table_prefix) > 0 and record_deletion_required:  # Table already existed and we are in a test environment
                test_utils_logger.info(f"Table '{table_name}' already exists. Deleting all existing records...")
                # Delete all existing records in the table
                AirtableUtils.delete_all_records_in_table(
                    base_id=AIRTABLE_APP_BASE_ID,
                    airtable_token=AIRTABLE_API_KEY,
                    table_name=table_name
                )
                test_utils_logger.info(f"All records deleted from table '{table_name}'")
            else:
                test_utils_logger.info(f"Table '{table_name}' created successfully")
        else:
            test_utils_logger.error(f"Failed to create/access table '{table_name}'")

    @classmethod
    def initialize_test_env(cls):
        # Add any one-time setup code here
        # Create test tables. If they exist, delete them and create new ones
        # tables to create: Patients, Nurses
        # Create nurses table with actual fields used in tests

        SpeakcareEnv.load_env()

        with open('tests/nurses.json', 'r') as f:
            nurses = json.load(f)
            test_utils_logger.info(f"Creating and clearing nurses table: {nurses}")
            cls.create_and_clear_table(nurses, "NurseID")
        
        with open('tests/patients.json', 'r') as f:
            patients = json.load(f)
            test_utils_logger.info(f"Creating and clearing patients table: {patients}")
            cls.create_and_clear_table(patients, "PatientID")

class AirtableUtils():
    def create_airtable_table(base_id, airtable_token, table_name, fields, id_field_name):
        url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"
        headers = {
            "Authorization": f"Bearer {airtable_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "name": table_name,
            # "fields": airtable_fields
            "fields": fields
        }

        test_utils_logger.info(f"sending create table request to url: {url}, header: {headers}, payload: {payload}")
        response = requests.post(url, headers=headers, json=payload)
        success = False
        record_deletion_required = False
        if response.status_code == 422 and "DUPLICATE_TABLE_NAME" in response.text:
            test_utils_logger.info(f"⚠️ Table '{table_name}' already exists.")
            success = True
            record_deletion_required = True
        elif response.status_code == 200:
            test_utils_logger.info("✅ Airtable Table created successfully.")
            success = True
            record_deletion_required = False
        else:
            test_utils_logger.info(f"❌ Error creating table: {response.status_code}")
            test_utils_logger.info(response.text)
            return False, False

        # # configure id field to be autonumber
        # body = {
        #     "type": "autoNumber",
        #     "name": id_field_name
        # }
        # url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables/{table_name}/fields"
        # headers = {
        #     "Authorization": f"Bearer {airtable_token}",
        #     "Content-Type": "application/json"
        # }
        # response = requests.post(url, headers=headers, json=body)
        # if response.status_code == 200:
        #     test_utils_logger.info(f"✅ ID field '{id_field_name}' configured as autonumber")
        # else:
        #     test_utils_logger.info(f"❌ Error configuring id field '{id_field_name}' as autonumber: {response.status_code}")
        #     test_utils_logger.info(response.text)

        return success, record_deletion_required

    @staticmethod
    def delete_all_records_in_table(base_id, airtable_token, table_name):
        """
        Delete all records from an existing Airtable table
        
        Args:
            base_id: Airtable base ID
            airtable_token: Airtable API token
            table_name: Name of the table to clear
            
        Returns:
            bool: True if successful, False otherwise
        """
        
        # First, get all records from the table
        url = f"https://api.airtable.com/v0/{base_id}/{table_name}"
        headers = {
            "Authorization": f"Bearer {airtable_token}",
            "Content-Type": "application/json"
        }
        
        try:
            # Get all records
            test_utils_logger.info(f"Getting all records from table '{url}, headers: {headers}'")
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                test_utils_logger.error(f"Failed to get records from table '{table_name}': {response.status_code}")
                return False
            
            records = response.json().get('records', [])
            if not records:
                test_utils_logger.info(f"Table '{table_name}' is already empty")
                return True
            
            # Delete all records
            record_ids = [record['id'] for record in records]
            test_utils_logger.info(f"Deleting {len(record_ids)} records from table '{table_name}'")
            test_utils_logger.info(f"Deleting {record_ids} records from table '{table_name}'")
            
            # Airtable allows deleting multiple records in one request
            records_params = '&'.join([f'records[]={record_id}' for record_id in record_ids])
            delete_url = f"https://api.airtable.com/v0/{base_id}/{table_name}?{records_params}"
            test_utils_logger.info(f"Deleting all records from table '{delete_url}, headers: {headers}'")

            delete_response = requests.delete(delete_url, headers=headers)
            if delete_response.status_code == 200:
                test_utils_logger.info(f"Successfully deleted {len(record_ids)} records from table '{table_name}'")
                return True
            else:
                test_utils_logger.error(f"Failed to delete records from table '{table_name}': {delete_response.status_code}")
                test_utils_logger.info(delete_response.text)
                return False
                
        except Exception as e:
            test_utils_logger.error(f"Error deleting records from table '{table_name}': {str(e)}")
            return False
