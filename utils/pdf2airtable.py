import os
import re
import json
import pdfplumber
import pytesseract
from PIL import Image
from dotenv import load_dotenv
from pdf2image import convert_from_path
import requests
import openai
from openai import OpenAI
import httpx
import sys

# === Load environment ===
def load_env():
    load_dotenv()
    openai.api_key = os.getenv("OPENAI_API_KEY")
    return {
        "AIRTABLE_TOKEN": os.getenv("AIRTABLE_API_KEY"),
        "BASE_ID": os.getenv("AIRTABLE_APP_BASE_ID"),
        "OPENAI_MODEL": os.getenv("OPENAI_MODEL", "gpt-4o-mini-2024-07-18")
    }

# === PDF Text Extraction ===
def extract_text_from_pdf(pdf_path):
    extracted_text = []
    with pdfplumber.open(pdf_path) as pdf:
        images = convert_from_path(pdf_path)
        for i, (page, img) in enumerate(zip(pdf.pages, images)):
            # Extract text from PDF
            text = page.extract_text() or ""
            
            # Extract text from image using OCR
            ocr_text = pytesseract.image_to_string(img, lang="eng").strip()
            
            # Combine all extracted information
            combined = f"--- Page {i+1} ---\n{text}\n\n--- OCR Content ---\n{ocr_text}"
            extracted_text.append(combined)
    return "\n".join(extracted_text)

# === OpenAI Extraction ===
def openai_extract_json(text, openai_model):
    openai_client = OpenAI()
    system_prompt = """
        You are an expert in clinical form extraction.

        Given OCR or noisy form text, return a FLAT JSON object.
        Your job is:
        - Preserve the full field name exactly as it appears in the document, including section titles and sub-sections.
        - For each field, identify its type:
            * If it's a checkbox, return true/false
            * If it's a multi-select field, return an array of ALL selected options
            * If it's a text field, return the text value, even if it's empty (return empty string "")
        - For multi-select fields, make sure to capture ALL options that are selected, not just the first few
        - Pay special attention to lists of options and capture all selected items
        - If you see multiple options selected in a section, include all of them in the array
        - Group Focus, Goal, and all Interventions into a single Multi-Select list under the Care Plan or Section name.
        - Avoid creating your own field names.
        - IMPORTANT: Always include ALL fields from the form, even if they are empty. Do not skip any fields.
        Make sure that the words you return are real words and that everything makes sense.
        Return only a valid JSON object.
        """

    try:
        response = openai_client.chat.completions.create(
            model=openai_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            temperature=0.2,
            max_tokens=4096,
            timeout=60
        )
        content = response.choices[0].message.content.strip()
        match = re.search(r'\{.*\}', content, re.DOTALL)
        return json.loads(match.group(0)) if match else {}
    except (openai.APITimeoutError, httpx.TimeoutException) as e:
        print(f"❌ OpenAI request timed out: {str(e)}")
        return {}

# === Flatten JSON ===
def flatten_json(y, parent_key='', sep='_'):
    items = []
    if isinstance(y, dict):
        if "Focus" in y and "Goal" in y and "Interventions" in y:
            fields = []
            if y["Focus"]:
                fields.append(f"Focus - {y['Focus']}")
            if y["Goal"]:
                fields.append(f"Goal - {y['Goal']}")
            for intervention in y.get("Interventions", []):
                fields.append(f"Intervention - {intervention}")
            clean_name = parent_key.strip()
            items.append((clean_name, fields))
        elif parent_key == "Safety Status":
            # Include all Safety Status options in the multi-select
            selected_items = []
            for k, v in y.items():
                if isinstance(v, bool):
                    selected_items.append(k)
            items.append(("Safety Status", selected_items))
        else:
            for k, v in y.items():
                new_key = f"{parent_key} {k}".strip() if parent_key else k
                if isinstance(v, dict):
                    items.extend(flatten_json(v, new_key, sep=sep).items())
                elif isinstance(v, list) and len(v) > 0:
                    items.append((new_key, v))
                else:
                    # Include all values, including empty strings
                    items.append((new_key, v))
    else:
        # Include all values, including empty strings
        items.append((parent_key, str(y)))
    return dict(items)

# === Create Airtable Table ===
def create_airtable_table(base_id, airtable_token, table_name, flat_json):
    url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"
    headers = {
        "Authorization": f"Bearer {airtable_token}",
        "Content-Type": "application/json"
    }

    fields = []
    # Primary field first
    fields.append({
        "name": "Record Name",
        "type": "singleLineText"
    })

    for idx, (name, value) in enumerate(flat_json.items(), start=1):
        # Remove special characters and sanitize field name for Airtable
        safe_name = re.sub(r'[<>/&?*#@$%^(){}[\]|\\]', '', name.strip())  # Remove special characters
        safe_name = re.sub(r'\s+', ' ', safe_name)  # Replace multiple spaces with single space
        safe_name = safe_name.strip()  # Remove leading/trailing spaces
        safe_name = safe_name[:255]  # Limit length to 255 characters
        
        if name == "Safety Status":
            # Create multi-select field with all possible options
            fields.append({
                "name": safe_name,
                "type": "multipleSelects",
                "options": {
                    "choices": [
                        {"name": "ID band on"},
                        {"name": "call bell within reach"},
                        {"name": "all alarms assessed and verified"},
                        {"name": "environmental safety check"},
                        {"name": "side rails up"},
                        {"name": "fall precautions initiated/maintained"},
                        {"name": "bed alarm"},
                        {"name": "bed in low position"},
                        {"name": "cardiac monitor alarms on"},
                        {"name": "telesitter"}
                    ]
                }
            })
        elif isinstance(value, bool):
            # Handle checkbox fields as single select
            fields.append({
                "name": safe_name,
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Yes"},
                        {"name": "No"}
                    ]
                }
            })
        elif isinstance(value, list) and all(isinstance(i, str) for i in value) and len(value) > 0:
            # Handle multi-select fields
            choices = [{"name": re.sub(r'[<>]', '', v.strip())[:100]} for v in value]
            fields.append({
                "name": safe_name,
                "type": "multipleSelects",
                "options": {"choices": choices}
            })
        elif isinstance(value, str) and value == "":
            # Handle empty strings as single line text
            fields.append({
                "name": safe_name,
                "type": "singleLineText"
            })
        else:
            # Handle other text fields as multiline
            fields.append({
                "name": safe_name,
                "type": "multilineText"
            })

    payload = {
        "name": table_name,
        "fields": fields
    }

    # print(json.dumps(payload, indent=2))  # Debug print if needed

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 422 and "DUPLICATE_TABLE_NAME" in response.text:
        print(f"⚠️ Table '{table_name}' already exists.")
        return True
    elif response.status_code == 200:
        print("✅ Airtable Table created successfully.")
        return True
    else:
        print(f"❌ Error creating table: {response.status_code}")
        print(response.text)
        return False

# === Insert Record into Airtable ===
def insert_record(base_id, airtable_token, table_name, flat_json):
    url = f"https://api.airtable.com/v0/{base_id}/{table_name}"
    headers = {
        "Authorization": f"Bearer {airtable_token}",
        "Content-Type": "application/json"
    }

    prepared_json = {}

    # Auto-fill "Record Name" with a simple value (like "Imported Record")
    prepared_json["Record Name"] = "Imported Record"

    for key, value in flat_json.items():
        # Sanitize field name using the same rules as create_airtable_table
        safe_key = re.sub(r'[<>/&?*#@$%^(){}[\]|\\]', '', key.strip())  # Remove special characters
        safe_key = re.sub(r'\s+', ' ', safe_key)  # Replace multiple spaces with single space
        safe_key = safe_key.strip()  # Remove leading/trailing spaces
        safe_key = safe_key[:255]  # Limit length to 255 characters
        
        if isinstance(value, bool):
            # Convert boolean to Yes/No for single select
            prepared_json[safe_key] = "Yes" if value else "No"
        elif isinstance(value, list) and all(isinstance(i, str) for i in value):
            # Limit each choice to 100 characters
            prepared_json[safe_key] = [v[:100] for v in value]
        else:
            prepared_json[safe_key] = str(value) if not isinstance(value, str) else value

    payload = {"records": [{"fields": prepared_json}]}

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        print("✅ Record inserted successfully.")
    else:
        print(f"❌ Error inserting record: {response.status_code}")
        print(response.text)

# === Main Processing Function ===
def process(pdf_path, table_name="FormData"):
    env_vars = load_env()
    print(f"🧾 Extracting from PDF: {pdf_path}")
    text = extract_text_from_pdf(pdf_path)
    print('text extracted', text)
    print("🤖 Sending to OpenAI...")
    json_data = openai_extract_json(text, env_vars['OPENAI_MODEL'])

    if not json_data:
        print("❌ No JSON data extracted. Stopping.")
        return

    print("📋 JSON extracted:")
    print(json.dumps(json_data, indent=2))

    flat_json = flatten_json(json_data)

    if create_airtable_table(env_vars['BASE_ID'], env_vars['AIRTABLE_TOKEN'], table_name, flat_json):
        insert_record(env_vars['BASE_ID'], env_vars['AIRTABLE_TOKEN'], table_name, flat_json)

# === CLI Entry Point ===
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python simple_pdf_to_airtable.py <pdf_path>")
    else:
        process(sys.argv[1])
