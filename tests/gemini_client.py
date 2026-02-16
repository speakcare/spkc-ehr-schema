import os
import logging
import json
from typing import Any, Dict, List
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# Initialize Native Gemini Client
# It automatically picks up GEMINI_API_KEY from environment
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Use Gemini-specific naming
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash") 

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def get_schema_depth(schema: Any) -> int:
    """Calculate the maximum nesting depth of a JSON schema."""
    if not isinstance(schema, dict) or "properties" not in schema:
        return 0
    
    max_depth = 0
    properties = schema.get("properties", {})
    for prop_schema in properties.values():
        if isinstance(prop_schema, dict):
            # If it's an object with properties, recurse
            if prop_schema.get("type") == "object":
                max_depth = max(max_depth, 1 + get_schema_depth(prop_schema))
            # If it's an array, check the items
            elif prop_schema.get("type") == "array" and "items" in prop_schema:
                max_depth = max(max_depth, 1 + get_schema_depth(prop_schema["items"]))
    
    return max_depth

def gemini_native_chat_completion(
    system_prompt: str = "You are an expert filling json objects according to the provided json schema.",
    user_prompt: str = None,
    json_schema: dict = None
) -> list:
    if not user_prompt or not json_schema:
        raise ValueError("user_prompt and json_schema are required")

    depth = get_schema_depth(json_schema)
    # Check for Gemini's depth limit (typically very low for strict structured output)
    use_strict = os.getenv("GEMINI_STRICT_SCHEMA", "false").lower() == "true"
    
    if use_strict and depth > 2: # Very conservative limit
        logger.warning(f"Schema depth {depth} might exceed Gemini limit. Switching to non-strict mode (schema in prompt) unless forced.")
        use_strict = False

    logger.info(f"Calling Native Gemini API model '{GEMINI_MODEL}' (Depth: {depth}, Strict: {use_strict})")

    if use_strict:
        # Configure the native generation config with strict schema enforcement
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type='application/json',
            response_json_schema=json_schema,
            temperature=float(os.getenv("GEMINI_TEMPERATURE", 0.2)),
            max_output_tokens=int(os.getenv("GEMINI_MAX_TOKENS", 8192)),
        )
        final_user_prompt = user_prompt
    else:
        # Move schema to prompt and use regular JSON mode
        schema_json = json.dumps(json_schema, indent=2)
        final_system_prompt = f"{system_prompt}\n\nYou must output a JSON object that strictly follows this JSON schema:\n{schema_json}"
        final_user_prompt = user_prompt
        
        config = types.GenerateContentConfig(
            system_instruction=final_system_prompt,
            response_mime_type='application/json',
            temperature=float(os.getenv("GEMINI_TEMPERATURE", 0.2)),
            max_output_tokens=int(os.getenv("GEMINI_MAX_TOKENS", 8192)),
        )

    try:
        # Generate content directly
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=final_user_prompt,
            config=config
        )

        # Gemini returns a single response object by default
        content = response.text.strip()
        
        # Clean up possible markdown formatting if not in strict mode
        if not use_strict:
            if content.startswith("```"):
                # Remove markdown code blocks
                lines = content.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                content = "\n".join(lines).strip()
        
        # Format to match your original function's return structure
        response_choices = [{
            "role": "model",
            "content": content,
            "finish_reason": "stop", # Simplified for native comparison
            "index": 0
        }]
        
        logger.info("Gemini native call complete")
        return response_choices

    except Exception as e:
        logger.error(f"Gemini API Error: {str(e)}")
        raise e