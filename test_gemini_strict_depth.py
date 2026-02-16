import os
import json
import logging
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
# Using the model defined in env or defaulting to gemini-2.0-flash
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

def test_strict_mode_with_schema(schema_path):
    print(f"Testing schema: {schema_path}")
    
    if not os.path.exists(schema_path):
        print(f"FAILED! File not found: {schema_path}")
        return

    with open(schema_path, 'r') as f:
        json_schema = json.load(f)
    
    system_prompt = "You are an expert filling json objects according to the provided json schema."
    user_prompt = "Fill in the assessment data for a hypothetical patient based on the schema."
    
    # Configure strict generation
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type='application/json',
        response_json_schema=json_schema,
        temperature=0.2,
        max_output_tokens=8192,
    )
    
    try:
        print(f"Calling Gemini API ({GEMINI_MODEL}) in STRICT mode...")
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=user_prompt,
            config=config
        )
        print("SUCCESS! Gemini accepted the schema in strict mode.")
    except Exception as e:
        print("FAILED! Gemini rejected the schema in strict mode.")
        print(f"Error: {e}")

if __name__ == "__main__":
    split_dir = "test_outputs/split_sections"
    if os.path.exists(split_dir):
        print(f"Testing split sections in {split_dir}...")
        for filename in sorted(os.listdir(split_dir)):
            if filename.endswith(".json"):
                print("=" * 40)
                test_strict_mode_with_schema(os.path.join(split_dir, filename))
    else:
        print(f"Directory not found: {split_dir}")
