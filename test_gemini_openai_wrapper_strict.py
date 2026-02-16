import os
import json
import logging
from dotenv import load_dotenv
import sys

# Add current dir to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tests.gemini_openai_client import openai_chat_completion

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_wrapper_strict_mode(schema_path):
    print(f"Testing schema with Gemini OpenAI Wrapper: {schema_path}")
    
    if not os.path.exists(schema_path):
        print(f"FAILED! File not found: {schema_path}")
        return

    with open(schema_path, 'r') as f:
        json_schema = json.load(f)
    
    system_prompt = "You are an expert filling json objects according to the provided json schema."
    user_prompt = "Fill in the assessment data for a hypothetical patient based on the schema."
    
    try:
        print(f"Calling Gemini OpenAI Wrapper in STRICT mode...")
        response_choices = openai_chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            json_schema=json_schema
        )
        print("SUCCESS! Gemini OpenAI Wrapper accepted the schema in strict mode.")
    except Exception as e:
        print("FAILED! Gemini OpenAI Wrapper rejected the schema in strict mode.")
        print(f"Error: {e}")

if __name__ == "__main__":
    split_dir = "test_outputs/split_sections"
    if os.path.exists(split_dir):
        print(f"Testing split sections in {split_dir} using Gemini OpenAI Wrapper...")
        for filename in sorted(os.listdir(split_dir)):
            if filename.endswith(".json"):
                print("=" * 40)
                test_wrapper_strict_mode(os.path.join(split_dir, filename))
    else:
        print(f"Directory not found: {split_dir}")
