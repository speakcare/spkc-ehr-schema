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

def load_env():
    load_dotenv()
    openai.api_key = os.getenv("OPENAI_API_KEY")
    return {
        "AIRTABLE_TOKEN": os.getenv("AIRTABLE_API_KEY"),
        "BASE_ID": os.getenv("AIRTABLE_APP_BASE_ID"),
        "OPENAI_MODEL": os.getenv("OPENAI_MODEL", "gpt-4o-mini-2024-07-18")
    }

def extract_text_from_pdf(pdf_path):
    extracted_text = []
    with pdfplumber.open(pdf_path) as pdf:
        images = convert_from_path(pdf_path)
        for i, (page, img) in enumerate(zip(pdf.pages, images)):
            text = page.extract_text() or ""
            
            ocr_text = pytesseract.image_to_string(img, lang="eng").strip()
            
            combined = f"--- Page {i+1} ---\n{text}\n\n--- OCR Content ---\n{ocr_text}"

            extracted_text.append(combined)
    return "\n".join(extracted_text)

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
        - Always prefer a multi-select field over a single select field.
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
                    items.append((new_key, v))
    else:
        items.append((parent_key, str(y)))
    return dict(items)

def sanitize_field_name(name):
    safe_name = re.sub(r'[<>/&?*#@$%^(){}[\]|\\]', '', name.strip())  # Remove special characters
    safe_name = re.sub(r'\s+', ' ', safe_name)  # Replace multiple spaces with single space
    safe_name = safe_name.strip()  # Remove leading/trailing spaces
    safe_name = safe_name[:255]  # Limit length to 255 characters
    # Replace dots with spaces
    safe_name = safe_name.replace('.', ' ')
    # Replace forward slashes with spaces
    safe_name = safe_name.replace('/', ' ')
    return safe_name

def create_airtable_table(base_id, airtable_token, table_name, fields):
    url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"
    headers = {
        "Authorization": f"Bearer {airtable_token}",
        "Content-Type": "application/json"
    }

    # Convert field types to Airtable types
    airtable_fields = []
    used_names = set()
    name_mapping = {}  # Keep track of original name to actual name mapping
    
    # First, create a list of all field names and their counts
    name_counts = {}
    for field in fields:
        name = sanitize_field_name(field["name"])
        name_counts[name] = name_counts.get(name, 0) + 1
    
    # Reset counters for each name
    name_counters = {name: 1 for name in name_counts}
    
    for field in fields:
        original_name = field["name"]
        base_name = sanitize_field_name(original_name)
        
        # If this name appears multiple times, add a suffix
        if name_counts[base_name] > 1:
            name = f"{base_name} {name_counters[base_name]}"
            name_counters[base_name] += 1
        else:
            name = base_name
            
        name_mapping[original_name] = name
        
        airtable_field = {
            "name": name,
            "type": "singleLineText"  # Default type
        }

        if field["type"] == "multilineText":
            airtable_field["type"] = "multilineText"
        elif field["type"] == "singleLineText":
            airtable_field["type"] = "singleLineText"
        elif field["type"] == "checkbox":
            airtable_field["type"] = "singleSelect"
            airtable_field["options"] = {
                "choices": [
                    {"name": "Yes"},
                    {"name": "No"}
                ]
            }
        elif field["type"] == "singleSelect" and "options" in field:
            airtable_field["type"] = "singleSelect"
            airtable_field["options"] = field["options"]
        elif field["type"] == "multipleSelects" and "options" in field:
            airtable_field["type"] = "multipleSelects"
            airtable_field["options"] = field["options"]

        airtable_fields.append(airtable_field)

    payload = {
        "name": table_name,
        "fields": airtable_fields
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 422 and "DUPLICATE_TABLE_NAME" in response.text:
        print(f"⚠️ Table '{table_name}' already exists.")
        return True, name_mapping
    elif response.status_code == 200:
        print("✅ Airtable Table created successfully.")
        return True, name_mapping
    else:
        print(f"❌ Error creating table: {response.status_code}")
        print(response.text)
        return False, name_mapping

def insert_record(base_id, airtable_token, table_name, flat_json, name_mapping=None):
    url = f"https://api.airtable.com/v0/{base_id}/{table_name}"
    headers = {
        "Authorization": f"Bearer {airtable_token}",
        "Content-Type": "application/json"
    }

    prepared_json = {}

    prepared_json["Record Name"] = "Imported Record"

    for key, value in flat_json.items():
        if name_mapping and key in name_mapping:
            safe_key = name_mapping[key]
        else:
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

def process_json_file(json_path, table_name="FormData"):
    env_vars = load_env()
    print(f"📄 Processing JSON file: {json_path}")
    
    try:
        with open(json_path, 'r') as f:
            json_data = json.load(f)
    except json.JSONDecodeError:
        print("❌ Error: Invalid JSON file format")
        return
    except FileNotFoundError:
        print(f"❌ Error: File not found - {json_path}")
        return
    
    print("📋 JSON loaded successfully")
    print(json.dumps(json_data, indent=2))

    flat_json = flatten_json(json_data)

    success, name_mapping = create_airtable_table(env_vars['BASE_ID'], env_vars['AIRTABLE_TOKEN'], table_name, flat_json)
    if success:
        insert_record(env_vars['BASE_ID'], env_vars['AIRTABLE_TOKEN'], table_name, flat_json, name_mapping)

def process_harmony_json(json_path, table_name="Harmony_Exam_Section"):
    env_vars = load_env()
    print(f"📄 Processing Harmony JSON file: {json_path}")
    
    try:
        with open(json_path, 'r') as f:
            json_data = json.load(f)
    except json.JSONDecodeError:
        print("❌ Error: Invalid JSON file format")
        return
    except FileNotFoundError:
        print(f"❌ Error: File not found - {json_path}")
        return
    
    print("📋 JSON loaded successfully")

    fields = []
    fields.append({
        "name": "Record Name",
        "type": "singleLineText"
    })

    for field_def in json_data.get('fields', []):
        try:
            field_config = {
                "name": field_def["name"],
                "type": field_def["type"]
            }
            
            if "options" in field_def:
                if field_def["type"] in ["multipleSelects", "singleSelect"]:
                    choices = [{"name": choice["name"]} for choice in field_def["options"]["choices"]]
                    field_config["options"] = {"choices": choices}
                else:
                    field_config["options"] = field_def["options"]
            
            fields.append(field_config)
        except Exception as e:
            print(f"Error processing field: {field_def.get('name', 'unknown')}")
            print(f"Error details: {str(e)}")
            continue

    success, name_mapping = create_airtable_table(env_vars['BASE_ID'], env_vars['AIRTABLE_TOKEN'], table_name, fields)
    if success:
        record = {"Record Name": "Imported Record"}
        
        field_counts = {}
        
        for field in fields[1:]:  # Skip the Record Name field
            original_name = field["name"]
            mapped_name = name_mapping[original_name]
            
            # Initialize the field in the record
            if field["type"] == "checkbox":
                record[mapped_name] = "No"  # Default to No for checkbox fields
            elif field["type"] == "singleSelect":
                record[mapped_name] = field["options"]["choices"][0]["name"]
            elif field["type"] == "multipleSelects":
                record[mapped_name] = []
            else:
                record[mapped_name] = ""
        
        insert_record(env_vars['BASE_ID'], env_vars['AIRTABLE_TOKEN'], table_name, record, name_mapping)

def process(input_path, table_name="FormData"):
    env_vars = load_env()
    
    try:
        abs_path = os.path.abspath(input_path)
        if not os.path.exists(abs_path):
            print(f"❌ Error: File not found at path: {abs_path}")
            print("Please check that the file exists and the path is correct.")
            return
    except Exception as e:
        print(f"❌ Error processing file path: {str(e)}")
        return
    
    if abs_path.lower().endswith('.pdf'):
        print(f"🧾 Processing PDF file: {abs_path}")
        try:
            text = extract_text_from_pdf(abs_path)
            print("✅ Text extracted successfully")
            print("🤖 Sending to OpenAI...")
            json_data = openai_extract_json(text, env_vars['OPENAI_MODEL'])

            if not json_data:
                print("❌ No JSON data extracted. Stopping.")
                return

            print("📋 JSON extracted successfully")
            print("\nExtracted JSON data:")
            print(json.dumps(json_data, indent=2))
            print("\n")

            flat_json = flatten_json(json_data)

            if create_airtable_table(env_vars['BASE_ID'], env_vars['AIRTABLE_TOKEN'], table_name, flat_json):
                insert_record(env_vars['BASE_ID'], env_vars['AIRTABLE_TOKEN'], table_name, flat_json)
        except Exception as e:
            print(f"❌ Error processing PDF: {str(e)}")
            return
    
    elif abs_path.lower().endswith('.json'):
        try:
            if "Harmony" in abs_path:
                process_harmony_json(abs_path, table_name)
            else:
                process_json_file(abs_path, table_name)
        except Exception as e:
            print(f"❌ Error processing JSON: {str(e)}")
            return
    
    else:
        print("❌ Error: Unsupported file format. Please provide a PDF or JSON file.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pdf2airtable.py <pdf_path or json_path> [table_name]")
    else:
        input_path = sys.argv[1]
        table_name = sys.argv[2] if len(sys.argv) > 2 else "FormData"
        process(input_path, table_name)
