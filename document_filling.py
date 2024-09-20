from speakcare_emr_utils import EmrUtils
from speakcare_emr import SpeakCareEmr
import json
import openai
from dotenv import load_dotenv
import os
openai.api_key = os.getenv("OPENAI_API_KEY")
import re

def fill_schema_with_transcription_as_dict(transcription, schema):
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
    
    prompt = f"""
    You are given a transcription of a conversation related to a nurse's treatment of a patient. 
    Based on the transcription, fill in the following fields as dictionary if you are sure of the answers.
    If you are unsure of any field, please respond with "no answer".
    
    Transcription: {transcription}
    
    Schema template:
    {json.dumps(schema, indent=2)}
    
    Return a dictionary by filling in only the fields you are sure about. 
    Return a dictionary of field name and value, making sure the values are cast as per their correct type (number, text, etc.).
    If uncertain, use "no answer" as the value.
    """

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an expert in parsing medical transcription and filling treatment forms."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=1000
    )
    
    filled_schema_str = response['choices'][0]['message']['content'].strip()

    # print(filled_schema_str)

    cleaned_filled_schema_str = re.sub(r'```json|```', '', filled_schema_str).strip()

    try:
        filled_schema_dict = json.loads(cleaned_filled_schema_str)
        return filled_schema_dict
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return {}

if __name__ == "__main__":


    transcriptions = [
        # 1. Complete Information
        """
        The nurse measured the patient's weight using a standing scale. 
        The weight recorded was 160.2 pounds. The patient prefers to use imperial units.
        """,

        # 2. Missing Weight
        """
        The nurse used a mechanical lift to weigh the patient. 
        The patient requested the weight to be recorded in kilograms. 
        However, the scale was not working correctly, and no weight could be recorded.
        """,

        # 3. Missing Unit Type
        """
        The nurse weighed the patient using a bed scale, 
        and the weight was recorded as 73.5. The patient was cooperative throughout the process.
        """

        # 4. Complete Information
        """
        During the nurse’s visit, the patient was weighed using a sitting scale. 
        The recorded weight was 180.6 pounds. The patient expressed a preference for pounds over kilograms.
        """,

        # 5. Missing Scale Type
        """
        The patient's weight was measured as 55.4 kilograms during the evening shift. 
        """,

        # 6. Missing Scale and Unit
        """
        The nurse documented the patient’s weight during a routine check-up. 
        Unfortunately, the exact scale and unit were not recorded, but the weight was noted as 68.9.
        """,

        # 7. Complete Information
        """
        The nurse weighed the patient using a wheelchair scale, 
        and the recorded weight was 145.2 pounds. The patient requested to continue using pounds as the preferred unit.
        """,

        # 8. Missing Weight and Unit
        """
        The patient was weighed using a bath scale, but due to a discrepancy with the scale's calibration, 
        no accurate weight was recorded. The nurse plans to weigh the patient again the next day.
        """,

        # 9. Complete Information
        """
        The nurse used a mechanical lift to weigh the patient, 
        and the weight was documented as 120.4 kilograms. The patient was unable to stand and requested the weight in kilograms.
        """,

        # 10. Missing Unit
        """
        The nurse used a bed scale to measure the patient's weight, 
        which was recorded as 154.6. However, the unit (kilograms or pounds) was not noted in the record.
        """
    ]

    schema = EmrUtils.get_record_writable_schema(SpeakCareEmr.WEIGHTS_TABLE)

    for transcription in transcriptions:
        filled_schema_dict = fill_schema_with_transcription_as_dict(transcription, schema)
        print("-" * 80)
        print(f"Transcription:\n{transcription}")
        print("Filled Schema (as dictionary):")
        print(filled_schema_dict)
