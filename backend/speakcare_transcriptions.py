from speakcare_emr_utils import EmrUtils
from speakcare_emr import SpeakCareEmr
from stt import transcribe_audio
import json
import openai
from openai import OpenAI
from datetime import datetime, timezone
from os_utils import ensure_directory_exists
from dotenv import load_dotenv
import os
import traceback
from speakcare_logging import create_logger
from speakcare_emr_utils import EmrUtils
from models import RecordState, TranscriptState
import copy

import re
import argparse
import logging

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
DB_DIRECTORY = os.getenv("DB_DIRECTORY", "db")

logger = create_logger(__name__)
logger.setLevel(logging.DEBUG)

multupleSelectionSchemaExample = {
            "type": "multipleSelects",
            "name": "MOOD (CHECK ALL THAT APPLY)",
            "options": {
                "choices": [
                    {
                        "name": "Passive"
                    },
                    {
                        "name": "Depressed"
                    },
                    {
                        "name": "Elated"
                    },
                    {
                        "name": "Quiet"
                    },
                    {
                        "name": "Questioning"
                    },
                    {
                        "name": "Talkative"
                    },
                    {
                        "name": "Secure"
                    },
                    {
                        "name": "Homesick"
                    },
                    {
                        "name": "Wanders Mentally"
                    },
                    {
                        "name": "Hyperactive"
                    },
                    {
                        "name": "Non-verbal"
                    }
                ]
            }
        }
multupleSelectionResultExample = {"MOOD (CHECK ALL THAT APPLY)": ["Passive", "Depressed", "Elated"]}

def transcription_to_emr_schema(transcription: str, schema: dict) -> dict:

    """
    Fills a schema based on the conversation transcription, returning a dictionary.
    The dictionary contains field names as keys and the corresponding filled values as values,
    with each value cast to the appropriate type based on the schema definition.
    If the value is "no answer", the field is omitted from the final dictionary.
    
    Parameters:
        transcription (str): The conversation transcription.
        schema (JSON): The JSON schema template to fill.
        
    Returns:
        dict: Dictionary of the filled schema
    """
    
    prompt = f'''
    You are given a transcription of a conversation related to a nurse's treatment of a patient. 
    Based on the transcription, fill in the following fields as dictionary if you are sure of the answers.
    If you are unsure of any field, please respond with "no answer".
    
    Transcription: {transcription}
    
    Schema template:
    {json.dumps(schema, indent=2)}
    
    Return a dictionary by filling in only the fields you are sure about. 
    Return a dictionary of field name and value, making sure the values are cast as per their correct type (number, text, etc.).
    If uncertain, use "no answer" as the value.
    Please return the output as a valid JSON object. 
    Ensure all fields are filled in with the correct data types (number, text, etc.).
    Fileds of type "singleSelect" should have a value that is one of the options in the "choices" list.
    Fields of type 'multipleSelects' should have a value that is a JSON list with values that must be from the "choices" list.
    For example, here is a field of type "multipleSelects". This is the example schema:
    {json.dumps(multupleSelectionSchemaExample, indent=2)}
    and the result should be only from the list of choices values, for example this field response can be:
    {json.dumps(multupleSelectionResultExample, indent=2)}
    Or, if you're unsure about a field, use "no answer" as the value. 
    The full response must be a single valid JSON object and nothing else.

    '''
    client = OpenAI()
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an expert in parsing medical transcription and filling treatment forms."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=4096
    )
    logger.debug(f"OpenAI Response: {completion}")    
    filled_schema_str = completion.choices[0].message.content.strip()
    logger.debug(f"filled_schema_str: {filled_schema_str}")
    cleaned_filled_schema_str = re.sub(r'```json|```', '', filled_schema_str).strip()
    logger.debug(f"cleaned_filled_schema_str: {cleaned_filled_schema_str}")

    try:
        filled_schema_dict = json.loads(cleaned_filled_schema_str)
        return filled_schema_dict
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON: {e}")
        return {}


def create_emr_record(data: dict, transcript_id: int=None, dryrun: bool=False) -> int:
    """
    Create an EMR record based on the transcription and schema.
    
    Parameters:
        transcription (str): The transcription of the conversation.
        schema (dict): The schema for the EMR record.
        
    Returns:
        dict: The EMR record as a dictionary.
    """

    #required_fields = ['type', 'table_name', 'patient_name', 'nurse_name', 'fields']
    record = {}

    table_name = next(iter(data))
    logger.debug(f"Table name: {table_name}")

    fields = data[table_name]
    fields = {
        field: value for field, value in fields.items()
        if not (
            (isinstance(value, str) and value.lower() == "no answer") or
            (isinstance(value, list) and all(isinstance(item, str) and item.lower() == "no answer" for item in value)) or
            (isinstance(value, list) and all(isinstance(item, str) and item.lower() == "none" for item in value))
        )
    }
    record['fields'] = fields
    logger.debug(f"Fields: {fields}")

    # handle patient name
    patient_name = data[table_name].get('patient_name', None)
    if not patient_name or patient_name.lower() == "no answer":
        logger.info("Didn't get patient name using 'Alice Johnson' as default.")
        patient_name = "Alice Johnson"
    else:
        logger.info(f"Patient name found: {patient_name}")
        # Remove patient name from fields and put it at the top level of the record  
        del record['fields']['patient_name']
    
    foundPatientByName, foundPatientIdByName, patientEmrId = EmrUtils.lookup_patient(patient_name)
    if not foundPatientByName:
        logger.info(f"Patient {patient_name} not found in EMR. Setting to 'Alice Johnson' as default")
        patient_name = "Alice Johnson"

    record['patient_name'] = patient_name

    record['table_name'] = table_name
    # TODO: For now hardcoding nurse name, later we can get it from the transcription
    record['nurse_name'] = "Rebecca Jones"
    
    # handle table with sections
    if table_name in [SpeakCareEmr.ADMISSION_TABLE, SpeakCareEmr.FALL_RISK_SCREEN_TABLE, SpeakCareEmr.VITALS_TABLE]:
        assessment_name = table_name
        # This is an assessment table we need to handle sections as well
        record['type'] = 'ASSESSMENT'
        record['sections'] = []
        for key, value in data.items():
            # skip the assessment name as it is already handled above as the main table
            if key != assessment_name:
                logger.debug(f"Section: {key} fields: {value}")
                table_name = key
                section_fields = value
                section_fields = {
                    field: value for field, value in section_fields.items()
                    if not (
                        (isinstance(value, str) and value.lower() == "no answer") or
                        (isinstance(value, list) and all(isinstance(item, str) and item.lower() == "no answer" for item in value)) or
                        (isinstance(value, list) and all(isinstance(item, str) and item.lower() == "none" for item in value))
                    )
                    }
                record['sections'].append(
                    {
                        'table_name': table_name,
                        'fields': section_fields
                    }
                )
    else:
        record['type'] = 'MEDICAL_RECORD'
   
    logger.info(f"Record: {json.dumps(record, indent = 4)}")

    record_id, record_state, error = EmrUtils.create_record(record, transcript_id)    
    if not record_id:
        logger.error(f"Failed to create record {record} in EMR. Error: {error}")
        return None, record_state
    elif record_state is RecordState.ERRORS:
        logger.warning(f"Record {record_id} created with errors: {error}.")
        return record_id,record_state

    elif dryrun:
        logger.info("Dryrun mode enabled. Skipping EMR record creation.")
        return record_id, record_state
    else:
        logger.info(f"Record created successfully with ID: {record_id}")
        emr_record_id, record_state, error = EmrUtils.commit_record_to_emr(record_id)
        if not emr_record_id:
            logger.error(f"Failed to commit record {record_id} to EMR. Error: {error} Record state: {record_state}")
        else:
            logger.info(f"Record id {record_id} committed successfully to EMR with ID: {emr_record_id}")

    return record_id, record_state


def transcription_to_emr(input_file: str, output_file: str, table_name: str, dryrun=False):
    """
    Convert a transcription from a file to a JSON file.
    
    Parameters:
        input_file (str): The input file containing the transcription.
        output_file (str): The output JSON file to write the converted transcription.
    """
    transcription = None
        

    try:
        with open(input_file, "r") as file:
            lines = file.readlines()

        if not lines:
            raise ValueError("No transcription found in the input file.")
        # Join the lines to form a single string
        transcription = " ".join(line.strip() for line in lines)
        logger.debug(f"Transcription:\n{transcription}")
        # Write the transcript to the Transcript database
        transcript_id, err = EmrUtils.add_transcript(transcription)
        if not transcript_id:
            logger.error(f"Failed to create transcript: {err}")
            raise ValueError(err)

        schema = EmrUtils.get_record_writable_schema(table_name)
        if not schema:
            raise ValueError(f"Invalid table name: {table_name}")
        logger.debug(f"Schema: {schema}")
        
        filled_schema_dict = transcription_to_emr_schema(transcription, schema)
        if not filled_schema_dict:
            err = f"Failed to fill schema of table {table_name} with transcription."
            logger.error(err)
            raise ValueError(err)
        logger.debug(f"Filled Schema: {filled_schema_dict}")
        
        with open(output_file, "w") as json_file:
            json.dump(filled_schema_dict, json_file, indent=4)
        logger.info(f"Transcription saved to {output_file}")

        record_id, record_state = create_emr_record(data=filled_schema_dict, transcript_id=transcript_id, dryrun=dryrun)
        if not record_id:
            err = f"Failed to create EMR record for table {table_name}. from data {filled_schema_dict}"
            logger.error(err)
            raise ValueError(err)
        
    except Exception as e:
        logger.error(f"Error occurred during transcription to EMR: {e}")
        traceback.print_exc()
        return None
    logger.info(f"EMR record created successfully with ID: {record_id}")
    return record_id

def main():
    output_dir = "out/jsons"
    supported_tables = EmrUtils.get_table_names()
    EmrUtils.init_db(db_directory=DB_DIRECTORY)
    
    parser = argparse.ArgumentParser(description='Speakcare transcription to EMR.')
    parser.add_argument('-o', '--output', type=str, default="output", help='Output file prefix (default: output)')
    parser.add_argument('-i', '--input', type=str, required=True, help='Input transcription file name (default: input)')
    parser.add_argument('-t', '--table', type=str, required=True, help=f'Table name (suported tables: {supported_tables}')
    parser.add_argument('-d', '--dryrun', action='store_true', help=f'If dryrun write JSON only and do not create EMR record')

    args = parser.parse_args()

    table_name = args.table
    
    input_file = args.input
    output_file_prefix = args.output
    dryrun = args.dryrun
    if dryrun:
        logger.info("Dryrun mode enabled. EMR record will not be created.")

    
    if table_name not in supported_tables:
        logger.error(f"Invalid table name: {table_name}. Supported tables: {supported_tables}")
        exit(1)
    

    # Get the current UTC time
    utc_now = datetime.now(timezone.utc)

    # Format the datetime as a string without microseconds and timezone
    utc_string = utc_now.strftime('%Y-%m-%dT%H:%M:%S')

    output_filename = f'{output_dir}/{output_file_prefix}.{utc_string}.json'

    ensure_directory_exists(output_dir) 
    transcription_to_emr(input_file=input_file, output_file=output_filename, table_name=table_name, dryrun=dryrun)


if __name__ == "__main__":
    main()

