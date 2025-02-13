from backend.spkc_emr_utils import EmrUtils
from backend.spkc_emr import SpeakCareEmr
import json
import openai
from openai import OpenAI
from datetime import datetime, timezone
from os_utils import ensure_directory_exists, Timer
from dotenv import load_dotenv
import os
import traceback
from backend.spkc_logging import SpeakcareLogger
from backend.spkc_emr_utils import EmrUtils
from models import RecordState, TranscriptState
import copy

import re
import argparse
import logging

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
DB_DIRECTORY = os.getenv("DB_DIRECTORY", "db")

logger = SpeakcareLogger('speakcare_transcriptions')

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

def transcription_to_emr_schema_old(transcription: str, schema: dict) -> dict:

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
    Based on the transcription, fill in the provided following fields as dictionary if you are sure of the answers.
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

def transcription_to_emr_schema(transcription: str, schema: dict) -> dict:

    """
    Splits the schema into main shcema and sections schema.
    Calls the OpenAI API for each of them separatly and then packs the responses together in a single dict.
    We do this to workaround the 100 parameters limit of OpenAI.
    """
    main_schema = copy.deepcopy(schema)
    # remove the sections so we can call the OpenAI API for the main schema without the sections
    if 'properties' in main_schema and 'sections' in main_schema['properties']:
        logger.debug(f"Removing sections from main schema")
        del main_schema['properties']['sections']
        # remove the sections from the required fields as well
        if 'required' in main_schema:
            main_schema['required'] = [field for field in main_schema['required'] if field != 'sections']
        
    logger.debug(f"main_schema: {json.dumps(main_schema, indent=4)}")

    record = __transcription_to_emr_json_schema(transcription, main_schema)
    
    sections = schema.get('properties', {}).get('sections', {}).get('properties', {})
    if sections:
        record['sections'] = {}
        # iterate the sections and call the OpenAI API for each of them
        for section_name, section_schema in sections.items():
            section = __transcription_to_emr_json_schema(transcription, section_schema)
            record['sections'][section_name] = section
    
    logger.debug(f"record: {json.dumps(record, indent=4)}")
    return record

temperature_example = {
    "Temperatures": {
            "fields": {
                "Units": "Fahrenheit",
                "Degrees": None,
                "Route": "Oral"
            }
        },
}

temperature_null = { 
    "Temperatures": {
            "fields": None
        }
}

pulse_example = {
    "Pulses": {
            "fields": {
                "Pulse": None,
                "PulseType": "Regular"
            }
        }
}

pulse_none = {
    "Pulses": {
            "fields": None
        }
}

blood_sugar_example = {
    "Blood Sugars": {
            "fields": {
                "SugarLevel": None
            }
        },
}

blood_sugar_none = {
    "Blood Sugars": {
            "fields": None
        },
}

admission_demographics_example = {
        "Admission: SECTION 1. DEMOGRAPHICS": {
            "fields": {
                "Admission Notes": None,
                "Transported by": None,
                "Accompanied by": None,
                "Diagnoses": None,
                "Admission Date": None
            }
        }
}

admission_demographics_none = {
        "Admission: SECTION 1. DEMOGRAPHICS": {
            "fields": None
        }
}


def __transcription_to_emr_schema_in_prompt(transcription: str, schema: dict) -> dict:

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
    You are given a Transcription of a conversation of a nurse providing care to a patient. 
    Based on the transcription, respond with a valid json object formatted according to the provided json_schema, and nothing else.
    Please fill in the json properties only where you are sure of the answers.
    If you are unsure of any property value, please respond with "null" for that property.
    If a property in an object has the word "reqired" in its description, that property is required to be filled, 
    if you cannot fill a "required" property correctly, please set the encompasing object value to null.
    In the following example:
    {temperature_example}
    The "Degrees" property is required, so if you are unsure of the value, set the entire "fields" object to null, this way:
    {temperature_null}
    In the following example:
    {pulse_example}
    The "Pulse" property is required, so if you are unsure of the value, set the entire "fields" object to null, this way:
    {pulse_none}
    In the following example:
    {blood_sugar_example}
    The "SugarLevel" property is required, so if you are unsure of the value, set the entire "fields" object to null, this way:
    {blood_sugar_none}

    Please apply the same logic to any "fields" object in the json_schema.
    
    Transcription: {transcription} 

    Json schema:
    {json.dumps(schema, indent=2)}      
    '''

    client = OpenAI()
    logger.info("Calling OpenAI API")
    response = client.chat.completions.create(
        model="gpt-4o-mini-2024-07-18",
        messages=[
            {"role": "system", "content": "You are an expert in parsing medical transcription and filling treatment forms."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_tokens=4096
    )
    logger.info("OpenAI done")
    logger.debug(f"OpenAI Response: {response}")    
    response_content = response.choices[0].message.content.strip()
    cleaned_response_content = re.sub(r'```json|```', '', response_content).strip()
    logger.debug(f"cleaned_response_content: {cleaned_response_content}")

    try:
        response_content_dict = json.loads(cleaned_response_content)
        logger.info(f"response_content_dict: {json.dumps(response_content_dict, indent=4)}")
        return response_content_dict
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON: {e}")
        return {}


    # if you have filled "null" to any of the required properties of a certain object, please set the encompasing object value to null.
    # Here are some examples to show you how to assign null to a "fields" object if a required property is missing:
    # In the following example:
    # {admission_demographics_example}
    # If the "Admission Date" property is required and you are unsure of its value, set the entire "fields" object to null, this way:
    # {admission_demographics_none}
    # In the following example:
    # {temperature_example}
    # If the "Degrees" property is required and you are unsure of its value, set the entire "fields" object to null, this way:
    # {temperature_null}
    # In the following example:
    # {pulse_example}
    # If the "Pulse" property is required and you are unsure of its value, set the entire "fields" object to null, this way:
    # {pulse_none}
    # In the following example:
    # {blood_sugar_example}
    # If the "SugarLevel" property is required and you are unsure of its value, set the entire "fields" object to null, this way:
    # {blood_sugar_none}
    # Please apply the same logic to any "fields" object in the json_schema.


    # If you are unsure of any property value, please respond with "null" for that property.
    # If a property in an object has the word "required" in its description, that property is required to be filled, 


    # If the values of all the properties of a specific "fields" object were set to null, please set the entire "fields" object to null.

    # If the values of all the properties of a specific "fields" object were set to null, please set the entire "fields" object to null.


def __transcription_to_emr_json_schema(transcription: str, schema: dict) -> dict:

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
    You are given a Transcription of a conversation of a nurse providing care to a patient. 
    Based on the transcription, respond with a valid json object formatted according to the provided json_schema, and nothing else.
    Please fill in the json properties if and only if you are sure of the answers.
    Do not assume any values, only fill in the properties that can explicitly be dervied from he transcription.
    If an issue is not mentioned, do not assume it is does not exist and do not fill in a value that implies the patient do not have that issue.
    In any case you cannot explicitly derive an answer from the transcription, you must set the value to null. 
    If the schema has sections, you must fill in the fields of each section separately.
    Step-by-step rules for each section:
    1. Start with "fields" set to `null`.
    2. If any field in the section has a non-null value, replace "fields" with an object containing only those non-null values.
    3. If all fields are null, ensure "fields" remains set to `null`.

    
    Transcription: {transcription}       
    '''
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "speakcare_transcription",
            "schema": schema,   
            "strict": True
        }
    }
    #logger.debug(f"response_format: {json.dumps(response_format, indent=4)}")
    #logger.debug(f"prompt: {prompt}")

    client = OpenAI()
    logger.info("Calling OpenAI API")
    response = client.chat.completions.create(
        model="gpt-4o-mini-2024-07-18",
        messages=[
            {"role": "system", "content": "You are an expert in parsing medical transcription and filling treatment forms."},
            {"role": "user", "content": prompt}
        ],
        response_format = response_format,
        temperature=0.2,
        max_tokens=4096
    )
    logger.info("OpenAI done")
    logger.debug(f"OpenAI Response: {response}")    
    response_content = response.choices[0].message.content

    try:
        response_content_dict = json.loads(response_content)
        logger.info(f"response_content_dict: {json.dumps(response_content_dict, indent=4)}")
        return response_content_dict
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON: {e}")
        return {}




def create_emr_record(record: dict, transcript_id: int=None, dryrun: bool=False) -> int:
    """
    Create an EMR record based on the transcription and schema.
    
    Parameters:
        transcription (str): The transcription of the conversation.
        schema (dict): The schema for the EMR record.
        
    Returns:
        dict: The EMR record as a dictionary.
    """

    table_name = record.get('table_name', None)
    if not table_name:
        error = f"Table name not found in data: {record}"
        logger.error(error)
        raise KeyError(error)
    
    logger.debug(f"Table name: {table_name}")

    patient_name = record.get('patient_name', None)
    if not patient_name:
        logger.info("Didn't get patient name using 'Alice Johnson' as default.")
        patient_name = "Alice Johnson"

    foundPatientByName, foundPatientIdByName, patientEmrId = EmrUtils.lookup_patient(patient_name)
    if not foundPatientByName:
        logger.info(f"Patient {patient_name} not found in EMR. Setting to 'Alice Johnson' as default")
        patient_name = "Alice Johnson"

    record["patient_name"] = patient_name
    # user nurse Rebecca jones as default nurse
    record['nurse_name'] = "Rebecca Jones"
    
    # if it is a multi secrtion assessment record
    if table_name in [SpeakCareEmr.ADMISSION_TABLE, SpeakCareEmr.FALL_RISK_SCREEN_TABLE, SpeakCareEmr.VITALS_TABLE]:
        record['type'] = 'ASSESSMENT'
    else:
        # simple medical record
        record['type'] = 'MEDICAL_RECORD'
   
    logger.debug(f"Record: {json.dumps(record, indent = 4)}")

    record_id, record_state, error = EmrUtils.create_record(record, transcript_id)    
    if not record_id:
        logger.error(f"Failed to create record {record} in EMR. Error: {json.dumps(error, indent=4)}")
        return None, record_state
    elif record_state is RecordState.ERRORS:
        logger.warning(f"Record {record_id} created with errors: {json.dumps(error, indent=4)}.")
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

        schema = EmrUtils.get_table_json_schema(table_name)
        if not schema:
            raise ValueError(f"Invalid table name: {table_name}")
        logger.debug(f"Schema: {json.dumps(schema, indent=4)}")
        
        timer = Timer()
        timer.start()
        filled_schema_dict = __transcription_to_emr_json_schema(transcription, schema)
        timer.stop()
        logger.info(f"Done calling __transcription_to_emr_json_schema in {timer.elapsed_time()} seconds")

        if not filled_schema_dict:
            err = f"Failed to fill schema of table {table_name} with transcription."
            logger.error(err)
            raise ValueError(err)
        
        with open(output_file, "w") as json_file:
            json.dump(filled_schema_dict, json_file, indent=4)
        logger.info(f"Transcription saved to {output_file}")

        record_id, record_state = create_emr_record(record=filled_schema_dict, transcript_id=transcript_id, dryrun=dryrun)
        if not record_id:
            err = f"Failed to create EMR record for table {table_name}. from data {filled_schema_dict}"
            logger.error(err)
            raise ValueError(err)
        
    except Exception as e:
        logger.log_exception("Error occurred during transcription to EMR", e)
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

