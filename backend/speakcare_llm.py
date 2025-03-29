import os
import json
import openai
from openai import OpenAI
from speakcare_logging import SpeakcareLogger
from speakcare_env import SpeakcareEnv  

SpeakcareEnv.load_env()
openai.api_key = os.getenv("OPENAI_API_KEY")

logger = SpeakcareLogger(__name__)


def openai_complete_schema_from_transcription(system_prompt: str, user_prompt: str,  transcription: str, schema: dict) -> dict:

    """
    Fills a schema based on the prompt and transcription, returning a dictionary.
    The dictionary contains field names as keys and the corresponding filled values as values,
    with each value cast to the appropriate type based on the schema definition.
    If the value is "no answer", the field is omitted from the final dictionary.
    
    Parameters:
        prompt (str): The prompt to send to the OpenAI API.
        transcription (str): The speech transcription.
        schema (JSON): The JSON schema template to fill.
        
    Returns:
        dict: Dictionary of the filled schema
    """
    
    prompt = f'{user_prompt} \n\nTranscription: {transcription}'
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "speakcare_transcription",
            "schema": schema,   
            "strict": True
        }
    }
    client = OpenAI()
    logger.info("Calling OpenAI API")
    response = client.chat.completions.create(
        model="gpt-4o-mini-2024-07-18",
        messages=[
            {"role": "system", "content": system_prompt},
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
