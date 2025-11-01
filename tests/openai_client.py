import json
import openai
from openai import OpenAI
import os
import argparse
from dotenv import load_dotenv
import logging

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
OPENAI_TEMPERATURE= float(os.getenv("OPENAI_TEMPERATURE", 0.2))
OPENAI_MAX_COMPLETION_TOKENS= int(os.getenv("OPENAI_MAX_COMPLETION_TOKENS", 4096))
OPENAI_MODEL= os.getenv("OPENAI_MODEL", "gpt-4o-mini-2024-07-18")

logger = logging.getLogger(__name__)    
logger.setLevel(logging.DEBUG)

__open_ai_default_system_prommpt= "You are an expert filling json objects according to the provided json schema."


openai_client = OpenAI()

def openai_chat_completion(system_prompt: str=None, user_prompt: str=None, json_schema: dict=None, num_choices: int = 1) -> dict:

    if system_prompt is None:
        system_prompt = __open_ai_default_system_prommpt
    if user_prompt is None:
        raise ValueError("user_prompt is required")
    if json_schema is None:
        raise ValueError("json_schema is required")

    logger.info(f"Calling OpenAI API model '{OPENAI_MODEL}', temperature '{OPENAI_TEMPERATURE}', max_completion_tokens '{OPENAI_MAX_COMPLETION_TOKENS}', num_choices '{num_choices}'")
    logger.debug(f"System Prompt: {system_prompt}")
    logger.debug(f"User Prompt: {user_prompt}")
    logger.debug(f"Json Schema: {json_schema}")

    # Prepare the arguments for the API call

    response_format= {
        "type": "json_schema",
        "json_schema": {
            "name": "speakcare_transcription",
            "schema": json_schema,   
            "strict": True
            }
        }

    chat_completion_args = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": OPENAI_TEMPERATURE,
        "max_completion_tokens": OPENAI_MAX_COMPLETION_TOKENS,
        "n": num_choices,
        "response_format": response_format
    }

    response = openai_client.chat.completions.create(**chat_completion_args)
    if response.choices[0].finish_reason != "stop":
        logger.error(f"OpenAI response finished with finish_reason: {response.choices[0].finish_reason}")
        logger.error(f"OpenAI response: {response.model_dump_json(indent=4) if hasattr(response, 'model_dump_json') else str(response)}")
        raise Exception(f"OpenAI response finished with finish_reason: {response.choices[0].finish_reason}")
    
    logger.info("OpenAI done")
    logger.debug(f"OpenAI Response: {response.model_dump_json(indent=4) if hasattr(response, 'model_dump_json') else str(response)}")
    response_choices = []
    for choice in response.choices:
        content = choice.message.content.strip()
        response_choices.append({
            "role": choice.message.role,
            "content": content,
            "finish_reason": choice.finish_reason,
            "index": choice.index
        })
        logger.info(f"response_choices[{choice.index}]: role: {choice.message.role}, finish_reason: {choice.finish_reason}")
        logger.debug(f"response_choices[{choice.index}]: content: {content}")
    return response_choices


