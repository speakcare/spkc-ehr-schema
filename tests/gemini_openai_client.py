

import json
import openai
from openai import OpenAI
import os
import argparse
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)    
logger.setLevel(logging.DEBUG)
OPENAI_TEMPERATURE= float(os.getenv("OPENAI_TEMPERATURE", 0.2))
OPENAI_MAX_COMPLETION_TOKENS= int(os.getenv("OPENAI_MAX_COMPLETION_TOKENS", 8192))



__open_ai_default_system_prommpt= "You are an expert filling json objects according to the provided json schema."

# Update these in your .env file:
# GEMINI_API_KEY = "your_google_ai_studio_key"
# GEMINI_MODEL = "gemini-2.0-flash" or "gemini-1.5-pro"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# The specific Base URL for Gemini's OpenAI-compatible endpoint
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

# Initialize with Gemini settings
openai_client = OpenAI(
    api_key=GEMINI_API_KEY,
    base_url=GEMINI_BASE_URL
)

def openai_chat_completion(system_prompt: str=None, user_prompt: str=None, json_schema: dict=None, num_choices: int = 1) -> dict:
    # ... (Your existing validation and logging logic) ...

    # Prepared for Gemini's compatible mode
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "speakcare_transcription",
            "schema": json_schema,
            "strict": True  # Gemini supports additionalProperties: false via strict
        }
    }

    chat_completion_args = {
        "model": GEMINI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": OPENAI_TEMPERATURE,
        # IMPORTANT: Use 'max_tokens' for Gemini. 
        # 'max_completion_tokens' is an alias but 'max_tokens' is standard for this endpoint.
        "max_tokens": OPENAI_MAX_COMPLETION_TOKENS, 
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


