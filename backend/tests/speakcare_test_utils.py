from dataclasses import field
import json
import os
import requests
from backend.speakcare_emr_tables import SpeakCareEmrTables
from backend.speakcare_env import SpeakcareEnv
from speakcare_logging import SpeakcareLogger

# Logger setup
test_utils_logger = SpeakcareLogger('test.utils')


class SpeakcareTestUtils:
    """ Class definition for SpeakcareTestUtils"""

    @classmethod
    def create_and_clear_table(cls, table):
        AIRTABLE_APP_BASE_ID = os.getenv('AIRTABLE_APP_BASE_ID')
        AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')
        
        emrTables = SpeakCareEmrTables()
        table_prefix = emrTables.get_person_table_prefix()
        table_name = table_prefix + "_" + table['name']
        test_table_rewrite_required = os.getenv('PERSON_TEST_TABLE_REWRITE', 'false').lower() == 'true'

        success, record_deletion_required = AirtableUtils.create_airtable_table(
            base_id=AIRTABLE_APP_BASE_ID, 
            airtable_token=AIRTABLE_API_KEY, 
            table_name=table_name, 
            fields=table['fields']
            )
        
        if success:
            if test_table_rewrite_required and len(table_prefix) > 0 and record_deletion_required:  # Table already existed and we are in a test environment
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
    def populate_test_table_from_original(cls, table):
        source_table_name = table['name']
        emrTables = SpeakCareEmrTables()
        table_prefix = emrTables.get_person_table_prefix()
        fields_to_skip = ['Photo', 'Age']
        fields_to_keep = [field['name'] for field in table['fields'] if field['name'] not in fields_to_skip]
        fields_to_strip = ['Nurses', 'Patients']
        test_table_rewrite_required = os.getenv('PERSON_TEST_TABLE_REWRITE', 'false').lower() == 'true'
        if test_table_rewrite_required and len(table_prefix) > 0:
            target_table_name = table_prefix + "_" + table['name']
            AirtableUtils.populate_table_from_another(
                base_id=os.getenv('AIRTABLE_APP_BASE_ID'),
                airtable_token=os.getenv('AIRTABLE_API_KEY'),
                source_table_name=source_table_name,
                target_table_name=target_table_name,
                fields_to_keep=fields_to_keep,
                fields_to_strip=fields_to_strip
            )

    @classmethod
    def initialize_test_env(cls):
        # Add any one-time setup code here
        # Create test tables. If they exist, delete them and create new ones
        # tables to create: Patients, Nurses
        # Create nurses table with actual fields used in tests

        SpeakcareEnv.load_env()

        emrTables = SpeakCareEmrTables()
        if not emrTables.is_test_env():
            return

        test_utils_logger.info(f"Initializing test environment")

        with open('tests/doctors.json', 'r') as f:
            table = json.load(f)
            test_utils_logger.info(f"Creating and clearing doctors table")
            test_utils_logger.debug(f"doctors table: {table}")
            cls.create_and_clear_table(table)

        cls.populate_test_table_from_original(table)

        with open('tests/nurses.json', 'r') as f:
            table = json.load(f)
            test_utils_logger.info(f"Creating and clearing nurses table")
            test_utils_logger.debug(f"nurses table: {table}")
            cls.create_and_clear_table(table)

        cls.populate_test_table_from_original(table)
        
        with open('tests/patients.json', 'r') as f:
            table = json.load(f)
            test_utils_logger.info(f"Creating and clearing patients table")
            test_utils_logger.debug(f"patients table: {table}")
            cls.create_and_clear_table(table)

        cls.populate_test_table_from_original(table)

        with open('tests/weights.json', 'r') as f:
            table = json.load(f)
            test_utils_logger.info(f"Creating and clearing weights table")
            test_utils_logger.debug(f"weights table: {table}")
            cls.create_and_clear_table(table)

        with open('tests/blood_pressures.json', 'r') as f:
            table = json.load(f)
            test_utils_logger.info(f"Creating and clearing blood-preassures table")
            test_utils_logger.debug(f"blood-preassures table: {table}")
            cls.create_and_clear_table(table)

        with open('tests/fall_risk_screen.json', 'r') as f:
            table = json.load(f)
            test_utils_logger.info(f"Creating and clearing fall-risk-screen-section-1 table")
            test_utils_logger.debug(f"fall-risk-screen-section-1 table: {table}")
            cls.create_and_clear_table(table)

        with open('tests/fall_risk_screen_section_1.json', 'r') as f:
            table = json.load(f)
            test_utils_logger.info(f"Creating and clearing fall-risk-screen-section-1 table")
            test_utils_logger.debug(f"fall-risk-screen-section-1 table: {table}")
            cls.create_and_clear_table(table)

class AirtableUtils():
    def create_airtable_table(base_id, airtable_token, table_name, fields):
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

        test_utils_logger.debug(f"sending create table request to url: {url}, header: {headers}, payload: {payload}")
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
            while True:
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
                record_ids = [record['id'] for record in records[:10]]
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

                records = records[10:]
                
        except Exception as e:
            test_utils_logger.error(f"Error deleting records from table '{table_name}': {str(e)}")
            return False

    @staticmethod
    def populate_table_from_another(base_id, airtable_token, source_table_name, target_table_name, 
                                   fields_to_keep=None, fields_to_strip=None, batch_size=10):
        """
        Populate one table from another with the same structure
        
        Args:
            base_id: Airtable base ID
            airtable_token: Airtable API token
            source_table_name: Name of the source table to read from
            target_table_name: Name of the target table to populate
            field_mapping: Optional dict mapping source field names to target field names
                          If None, assumes identical field names
            batch_size: Number of records to create in each batch (Airtable limit is 10)
            
        Returns:
            tuple: (success: bool, records_created: int, error_message: str)
        """
        
        headers = {
            "Authorization": f"Bearer {airtable_token}",
            "Content-Type": "application/json"
        }
        
        # try:
        if 1:
            # First, get all records from the source table
            source_url = f"https://api.airtable.com/v0/{base_id}/{source_table_name}"
            test_utils_logger.info(f"Getting all records from source table '{source_table_name}'")
            
            response = requests.get(source_url, headers=headers)
            if response.status_code != 200:
                error_msg = f"Failed to get records from source table '{source_table_name}': {response.status_code}"
                test_utils_logger.error(error_msg)
                return False, 0, error_msg
            
            source_records = response.json().get('records', [])
            if not source_records:
                test_utils_logger.info(f"Source table '{source_table_name}' is empty")
                return True, 0, "Source table is empty"
            
            test_utils_logger.info(f"Found {len(source_records)} records in source table '{source_table_name}'")
            test_utils_logger.info(f"fields_to_keep: {fields_to_keep}")
            test_utils_logger.info(f"source_records: {source_records}")
            
            # Transform records if field mapping is provided
            transformed_records = []
            for record in source_records:
                fields = record.get('fields', {})
                
                if fields_to_keep:
                    # Apply field mapping
                    transformed_fields = {}
                    for field in fields:
                        if field in fields_to_keep:
                            if field in fields_to_strip and isinstance(fields[field], list):
                                stripped_value = ",".join(fields[field])
                                transformed_fields[field] = stripped_value
                            else:
                                transformed_fields[field] = fields[field]
                        else:
                            # skip unknonw fields
                            pass            
                else:
                    # Use fields as-is
                    transformed_fields = fields.copy()
                
                transformed_records.append({"fields": transformed_fields})
            
            # Create records in batches in the target table
            target_url = f"https://api.airtable.com/v0/{base_id}/{target_table_name}"
            records_created = 0
            
            for i in range(0, len(transformed_records), batch_size):
                batch = transformed_records[i:i + batch_size]
                test_utils_logger.info(f"Creating batch {i//batch_size + 1} with {len(batch)} records")
                
                payload = {"records": batch}
                create_response = requests.post(target_url, headers=headers, json=payload)
                
                if create_response.status_code == 200:
                    batch_results = create_response.json().get('records', [])
                    records_created += len(batch_results)
                    test_utils_logger.info(f"Successfully created batch {i//batch_size + 1}: {len(batch_results)} records")
                else:
                    error_msg = f"Failed to create batch {i//batch_size + 1}: {create_response.status_code} - {create_response.text}"
                    test_utils_logger.error(error_msg)
                    return False, records_created, error_msg
            
            test_utils_logger.info(f"Successfully populated table '{target_table_name}' with {records_created} records from '{source_table_name}'")
            return True, records_created, ""
            
        # except Exception as e:
        #     error_msg = f"Error populating table '{target_table_name}' from '{source_table_name}': {str(e)}"
        #     test_utils_logger.error(error_msg)
        #     return False, records_created, error_msg

    @staticmethod
    def get_table_records(base_id, airtable_token, table_name):
        """
        Get all records from an Airtable table
        
        Args:
            base_id: Airtable base ID
            airtable_token: Airtable API token
            table_name: Name of the table to read from
            
        Returns:
            tuple: (success: bool, records: list, error_message: str)
        """
        
        url = f"https://api.airtable.com/v0/{base_id}/{table_name}"
        headers = {
            "Authorization": f"Bearer {airtable_token}",
            "Content-Type": "application/json"
        }
        
        try:
            test_utils_logger.info(f"Getting all records from table '{table_name}'")
            response = requests.get(url, headers=headers)
            
            if response.status_code != 200:
                error_msg = f"Failed to get records from table '{table_name}': {response.status_code}"
                test_utils_logger.error(error_msg)
                return False, [], error_msg
            
            records = response.json().get('records', [])
            test_utils_logger.info(f"Successfully retrieved {len(records)} records from table '{table_name}'")
            return True, records, ""
            
        except Exception as e:
            error_msg = f"Error getting records from table '{table_name}': {str(e)}"
            test_utils_logger.error(error_msg)
            return False, [], error_msg
