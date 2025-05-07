import sys
import os
import re
import json
# Get the parent directory of the current file
project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, project_dir)

from utils.pdf2airtable import extract_text_from_pdf
from backend.speakcare_openai import openai_chat_completion

# Airtable table schema
airtable_table_schema = {
      "name": "The name of the table",
      "description": "the description of the table",
      "fields": [
        {
            "name": "field1",
            "description": "field1 description",
            "type": "field1 type",
            "options": {"field type specific option" : "field type specific option value"}
        },
        {
            "name": "field2",
            "description": "field2 description",
            "type": "field2 type",
            "options": {"field type specific option" : "field type specific option value"}
        },
        {
            "name": "field3",
            "description": "field3 description",
            "type": "field3 type",
            "options": {"field type specific option" : "field type specific option value"}
        }
      ]
}
CONSTANT_FIELDS = [
    {"name": "RecordID", "type": "singleLineText"},
    {
        "name": "Patient", 
        "type": "multipleRecordLinks",
        "options": {
            "linkedTableId": "tbleNsgzYZvRy1st1"
        }
    },
    {   "name": "CreatedBy", 
        "type": "multipleRecordLinks",
        "options": {
            "linkedTableId": "tblku5F04AH4D9WBo"
        }
    },
    {
        "name": "SpeakCare",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "Draft", "color": "blueLight2"},
                {"name": "Approved", "color": "greenBright"},
                {"name": "Denied", "color": "redBright"}
            ]
        }
    }
]
airtable_table_temperature_example = {
    "name": "Temperatures",
    "description": "Temperatures",
    "fields": CONSTANT_FIELDS + [
        {"name": "Temperature", "description": "Temperature", "type": "number"},
        {"name": "TemperatureRoute", "description": "Temperature route", "type": "singleSelect", 
            "options": {
                "choices": [
                    {"name": "Oral"},
                    {"name": "Rectal"},
                    {"name": "Axillary"}
                ]
            }
        },
        {"name": "TemperatureUnits", "description": "Temperature units", "type": "singleSelect", "options": {
            "choices": [
                {"name": "Fahrenheit"},
                {"name": "Celsius"}
            ]
        }}
    ]
}

# checkbox field
airtable_checkbox_field_schema = {
      "name": "The name of the field",
      "description": "the description of the field",
      "type": "checkbox",
      "options": {
        "icon": "check",
        "color": "greenBright"
    }
}
airtable_checkbox_field_pacemaker_example = {
      "name": "Pacemaker device",
      "description": "check if the patient has a pacemaker device",
      "type": "checkbox",
      "options": {
        "icon": "check",
        "color": "greenBright"
    }
}

# multiline text field
airtable_multiline_text_fieldschema = {
      "name": "The name of the field",
      "description": "The description of the field",
      "type": "multilineText"
}
airtable_multiline_text_field_genital_exam_example = {
      "name": "Genital Exam",
      "description": "Decribe the genital exam",
      "type": "multilineText"
}
airtable_multiline_text_field_notes_example = {
      "name": "Notes",
      "description": "notes",
      "type": "multilineText"
}

# number field
airtable_number_field_schema = {
      "name": "The name of the field",
      "description": "The description of the field",
      "type": "number",
      "options": {
        "precision": 1
      }
}
airtable_number_field_temperature_example = {
      "name": "Temperature",
      "description": "Temperature",
      "type": "number",
      "options": {
        "precision": 1
      }
}

# single select field
airtable_single_select_field_schema = {
    "name": "The name of the field",
    "description": "the description of the field",
    "type": "singleSelect",
    "options": {
        "choices": [
          {
            "name": "choice1"
          },
          {
            "name": "choice2"
          },
          {
            "name": "choice3"

          },
          {
            "name": "choice4"
          }
        ]
    }
}
airtable_single_select_field_temperature_example = {
    "name": "Temperature route",
    "description": "Temperature route. Select one",
    "type": "singleSelect",
    "options": {
        "choices": [
          {
            "name": "Oral"
          },
          {
            "name": "Rectal"
          },
          {
            "name": "Axillary"
          },
          {
            "name": "Tympanic"
          },
          {
            "name": "Temporal artery"
          },
          {
            "name": "Forehead"
          },
          {
            "name": "Skin"
          }
        ]
    }
} 
airtable_single_select_field_meal_example = {
    "name": "Amount of meal eaten",
    "description": "Amount of meal eaten in percentage",
    "type": "singleSelect",
    "options": {
        "choices": [
          {
            "name": "0"
          },
          {
            "name": "25"
          },
          {
            "name": "50"
          },
          {
            "name": "75"
          },
          {
            "name": "100"
          }
        ]
    }
} 

# multiple select field
airtable_multiple_select_field_schema = {
    "name": "The name of the field",
    "description": "the description of the field",
    "type": "multipleSelects",
    "options": {
       "choices": [
          {
            "name": "choice1"
          },
          {
            "name": "choice2"
          },
          {
            "name": "choice3"

          },
          {
            "name": "choice4"
          }
        ]
    }
}
airtable_multiple_select_field_skin_integrity_example = {
    "name": "Skin integrity",
    "description": "Skin integrity. Select all that apply",
    "type": "multipleSelects",
    "options": {
       "choices": [
          {
            "name": "abnormal skin color and pigmentation"
          },
          {
            "name": "abnormal skin temperature"
          },
          {
            "name": "abnormal skin moisture"
          },
          {
            "name": "skin not intact"
          }
        ]
    }
}
airtable_multiple_select_field_safety_status_example = {
    "name": "SafetyStatus",
    "description": "Safety status. Select all that apply",
    "type": "multipleSelects",
    "options": {
        "choices": [
          {
            "name": "ID band on"
          },
          {
            "name": "call bell within reach"
          },
          {
            "name": "all alarms assessed and verified"
          },
          {
            "name": "environmental safety check"
          },
          {
            "name": "side rails up"
          },
          {
            "name": "fall precautions initiated/maintained"
          },
          {
            "name": "bed alarm"
          },
          {
            "name": "bed in low position"
          },
          {
            "name": "cardiac monitor alarms on"
          }
        ]
    }
}


def openai_convert_document_to_airtable_schema(document_text: str, customer: str) -> dict:
    system_prompt = f'''
        You are an expert in clinical form extraction.
        You are given a non structured text of a clinical form as a reference.
        Your job is to extract the form structure and create a structured JSON object that describes the metadata for airtable tables.
        Note that we are not interested in the data values, only the structure of the form.
        The JSON object must be in the valid format of an airtable table schema.
        An Airtable table schema is structured as a JSON object with the following properties:
        - name: the name of the table
        - description: the description of the table
        - fields: an array of fields
        This is a generic example of an airtable table schema 
        {airtable_table_schema}
        
        Each field in the fields array has the following properties:
        - name (required): the name of the field
        - description (optional): the description of the field
        - type (required): the type of the field
        - options (optional): the type specific options of the field. This may be optional or required depending on the type.

        All tables must have the following constant fields as their first fields in the fields array:
        {CONSTANT_FIELDS}
        This is an example of a Temperature table with the constant fields and specific fields for temperature:
        {airtable_table_temperature_example}
        Here is the supported field types and for each we provide a schema and one or two examples:
        1. Type: "checkbox"
            schema:
            {airtable_checkbox_field_schema}
            example: pacemaker device (check if the patient has a pacemaker device):
            {airtable_checkbox_field_pacemaker_example}
        2. Type: "multilineText"
            schema:
            {airtable_multiline_text_fieldschema}
            example 1: genital exam:
            {airtable_multiline_text_field_genital_exam_example}
            example 2: notes:
            {airtable_multiline_text_field_notes_example}
        3. Type: "number"
            schema:
            {airtable_number_field_schema}
            example: temperature:
            {airtable_number_field_temperature_example}
        4. Type: "singleSelect"
            schema:
            {airtable_single_select_field_schema}
            example 1: temperature route:
            {airtable_single_select_field_temperature_example}
            example 2: amount of meal eaten:
            {airtable_single_select_field_meal_example}
        5. Type: "multipleSelects"
            schema:
            {airtable_multiple_select_field_schema}
            example 1: skin integrity:
            {airtable_multiple_select_field_skin_integrity_example}
            example 2: safety status:
            {airtable_multiple_select_field_safety_status_example}
        
        Table creation steps:
        - Document hierarchy:
            + The document is organized in sections, gruops and questions. Each section is divided into groups of questions.
            + The hierarchy indexing is as follows:
                1. Section number and title for example: "2. Admission Details"
                2. Group letter (always a capital letter) for example: "G. Vital Signs" OR Group number and title for example: "2. Required Evaluations"
                3. Question ID is either a number or a number with a letter. For example: "7" or "12a". When there is a letter, it is always a lowercase letter.
                   When the question ID is a number with a letter it is a subsequent question of the question with the number. For example: "12a" is a subsequent question of "12".
                   Subsequent questions are meaningful only in the context of the question they are a subsequent question of.
                4. A multi question is a question that splits into multiple questions. For example:
                      "2. Most Recent Blood Pressure"
                         "Blood Pressure:"  "Date:"
                         "Position:"
                    This is split into 3 questions:
                      "2a. Most Recent Blood Pressure" (type: number)
                      "2b. Most Recent Blood Pressure.Date" (type: singleLineText)
                      "2c. Most Recent Blood Pressure.Position" (type: singleLineText)
                5. NOTE: Some documents do not have sections and there will be only groups and questions in the hierarchy.
        
        - Create the table schema for the document.
            1. The table name is the section title up to the first comma or dot. If the name has spaces, replace them with unndercores. 
               For example: "Admission Details, Orientation to Facility and Preferences" will be "Admission_Details"
            2. If there are no sections, use the document title as the table name.
            3. Use the customer name {customer} as a prefix for the table name. For example: "Customer.Admission_Details"    
            4. Add the constant fields as the first fields in the fields array.
            5. Add the other fields to the fields array according to the instructions to follow.
        
                
        - Field mapping:
            1. Group name is mapped into a singleLineText field with the name "<group letter>.<group name> Group". For example:
                "B.Therapy Care Plan Group"
            2. Question mapping:
               a. Questions have IDs, that could be a number (e.g. 12) or a number with letter (e.g. 7a).
               b. The field name must be prefixed with the full index hierarchy, for example: "<group letter>.<question ID>. <question text>" For example:
                  "1.B.2a. Therapy Care Plan"
            3. Field type is determined by the question and possible answers context
            4. Field descipriotn is an elaboration of the question.
            5. Decide the type of the field out of the provided types: "checkbox", "multilineText", "number", "singleSelect", "multipleSelects".
            6. Constructing the multiSelect and singleSelect fields:
                a. A question followed by multiple options is mapped to a select field.
                b. The multiple options can have either letters indexes. For example: a. Physical Therapy (PT) b. Occupational Therapy (OT) c. Speech Therapy (ST) 
                   Or, they can be mutiple text lines prefixed by one of the following words: "Focus:", "Goal:", "Interventions:", "Tasks:"
                c. If the answer options have letters indexes then then the the field options must be the options including the indexes. For example:
                    "bb. Monitored vital signs/oxygen saturation." is mapped to option name "bb. Monitored vital signs/oxygen saturation."
                d. If there are  multiple lines prefixed by letters that are directly under a group rather than a question, you should create a multi-select field
                   for the group name using the letters as the options. For example:
                   Z. SOB
                        1. Is the head of the bed elevated to prevent SOB while lying flat?
                            a. Yes
                            b. No
                        a. Shortness of breath or trouble breathing with exertion (e.g., walking, bathing, transferring)
                        b. Shortness of breath or trouble breathing when sitting at rest
                        c. Shortness of breath or trouble breathing when lying flat
                    In this case the question 1. Is the head of the bed elevated to prevent SOB while lying flat? is mapped to a single select yes/no field and 
                    the options a,b,c directly under the group Z. SOB are mapped to a multi-select field with the options a,b,c.
                e. A question followed by multiple text lines prefixed by one of the following words: "Focus:", "Goal:", "Interventions:", "Tasks:" 
                   MUST be mapped to a multi-select field with the options being the text lines, including the prefix word
                f. Simple Yes / No options are always mapped to a single select field with two options: "Yes" and "No".
                g. Non trivial options will be mapped to a multi-select field unless the context is clear that it should be a single select field. 
                h. When uncertain, always prefer a multi-select field.
                h. Make sure to capture ALL options that are provided in the document, not just the first few. 
                   Pay special attention to lists of options and capture all selected items.
            7. For subsequent questions like 10a, 7b, 8d etc. the description must be prefixed by the name of the parent question to maintain context. 
                - For example:
                    10. Cognitive Orientation -> name: "10. Cognitive Orientation", description: "Cognitive Orientation"
                    10a. Comatose Care Plan -> name: "10a. Comatose Care Plan", description: "Cognitive Orientation.Comatose Care Plan"
                - Another example:
                    1. Initial goals: -> name: "1. Initial goals", description: "Initial goals"
                    1a. If "other" selected, describe: -> name: "1a. If "other" selected, describe", description: "Initial goals. If "other" selected, describe"
               
            8. Multi questions with a single question ID, the question name must be prefixed by the parent question name For example:
              "3. Most Recent Pulse"
                 "Pulse:"  "Date:" 
                 "Pulse Type:" 
                 
              This should created 3 fields:
                 "3a. Most Recent Pulse" (type: number), 
                 "3b. Pulse Type" (type: singleLineText), 
                 "3c. Pulse Date" (type: singleLineText)
            9. Format the field according to the type including the options if required.
            10. General guidelines:
                a. IMPORTANT: Always include ALL fields from the form, even if they are empty. Do not skip any fields.
                b. Avoid creating your own field names.
                c. Make sure that the words you return are real words and that everything makes sense.
    '''
    table = openai_chat_completion(
        system_prompt=system_prompt,
        user_prompt=document_text,
    )
    return table


def remove_quotes_from_names_and_descriptions(obj):
    """
    Recursively remove all double and single quotes, backslashes, and forward slashes from 'name' and 'description' fields in a nested dict/list.
    If a slash is separated by spaces, remove it; otherwise, replace it with a space.
    Forward slash (/) is replaced with the word 'or'.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("name", "description") and isinstance(v, str):
                # Remove quotes
                v = v.replace('"', '').replace("'", "")
                # Replace forward slash with 'or'
                v = v.replace('/', ' or ')
                # Remove backslash if separated by spaces, otherwise replace with space
                v = re.sub(r'\s*\\\s*', ' ', v)
                obj[k] = v
            else:
                remove_quotes_from_names_and_descriptions(v)
    elif isinstance(obj, list):
        for item in obj:
            remove_quotes_from_names_and_descriptions(item)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input_path", type=str, required=True, help="Path to the input file to process")
    parser.add_argument("-p", "--pdf_file", action="store_true", help="Path to the PDF file to process")
    parser.add_argument("-a", "--convert_to_airtable", action="store_true", help="Convert the document to an airtable schema")
    parser.add_argument("-c", "--customer", type=str, default="Unknown", help="Customer name used in the table name")
    parser.add_argument("-d", "--output-dir", default=".", help="Directory to store output files")
    args = parser.parse_args()

    customer = ""
    if args.customer:
        customer = args.customer
    else:
        customer = "Unknown"

    output_dir = args.output_dir
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    if args.pdf_file:   
        text = extract_text_from_pdf(args.input_path)
        print(text)
        filename = os.path.basename(args.input_path).replace(".pdf", ".txt")
        filename = os.path.join(output_dir, filename)
        with open(filename, "w") as f:
            f.write(text)
        print(f"Text saved to {filename}")
        exit()
    elif args.convert_to_airtable:
        text = ""
        with open(args.input_path, "r") as f:
            text = f.read()
        response_choices = openai_convert_document_to_airtable_schema(text, customer)
        for response in response_choices:
            response_content = response.get("content", "").strip()
            print(f"response_content:\n{response_content}")
            if response_content:
                cleaned_response_content = re.sub(r'```json|```', '', response_content).strip()
                print("\n\n\n")
                print(f"cleaned_response_content:\n{cleaned_response_content}")
                response_dict = json.loads(cleaned_response_content)
                remove_quotes_from_names_and_descriptions(response_dict)
                output_filename = f"{response_dict.get('name', 'Unknown')}.json"
                output_filename = os.path.join(output_dir, output_filename)
                with open(output_filename, "w") as f:
                    json.dump(response_dict, f, indent=4)

