import pdfplumber
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import os
import json
import openai
import pandas as pd
import re
from openai import OpenAI
from dotenv import load_dotenv
from speakcare_logging import SpeakcareLogger

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", 0.2))
OPENAI_MAX_COMPLETION_TOKENS = int(os.getenv("OPENAI_MAX_COMPLETION_TOKENS", 4096))
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini-2024-07-18")

# OpenAI system prompt
SYSTEM_PROMPT = "You are an expert in medical transcription and form completion. The input comes from an OCR model and may contain errors—correct them accordingly. Provide only a valid JSON object with accurate syntax, without any explanations or additional text."

# Logger setup
logger = SpeakcareLogger('speakcare_openai')
openai_client = OpenAI()

def extract_json_from_response(response_text):
    """Extracts valid JSON from OpenAI response using regex."""
    match = re.search(r'\{.*\}', response_text, re.DOTALL)
    return match.group(0) if match else None

def openai_chat_completion(system_prompt: str, user_prompt: str) -> dict:
    """Calls OpenAI API and ensures a valid JSON output."""
    logger.info(f"Calling OpenAI API model '{OPENAI_MODEL}'")
    
    response = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=OPENAI_TEMPERATURE,
        max_tokens=OPENAI_MAX_COMPLETION_TOKENS,
        n=1
    )
    
    raw_response = response.choices[0].message.content.strip() if response.choices else ''
    logger.info(f"Raw OpenAI Response: {raw_response}")

    json_response = extract_json_from_response(raw_response)
    if not json_response:
        logger.error("OpenAI response does not contain valid JSON.")
        return {}

    try:
        return json.loads(json_response)
    except json.JSONDecodeError:
        logger.error("Failed to parse extracted JSON.")
        return {}

def extract_text_from_pdf(pdf_path):
    """Extracts text from a PDF, handling both text-based and scanned PDFs."""
    extracted_text = []
    with pdfplumber.open(pdf_path) as pdf:
        images = convert_from_path(pdf_path)
        for i, (page, img) in enumerate(zip(pdf.pages, images)):
            text = page.extract_text() or ""
            ocr_text = pytesseract.image_to_string(img, lang="eng").strip()
            combined_text = f"--- Page {i+1} ---\n{text}\n\n--- OCR Content ---\n{ocr_text}\n"
            extracted_text.append(combined_text)
    return "\n".join(extracted_text)

def clean_column_name(col_name):
    """Cleans and formats column names to be more readable."""
    col_name = col_name.replace("General_Admit_Info.", "").replace("_", " ").strip()
    col_name = re.sub(r"\.(\w)", lambda m: " " + m.group(1).upper(), col_name)  # Capitalize nested keys
    return col_name

def json_to_csv(json_data, csv_output_path):
    """Converts JSON data into a CSV with cleaned column names."""
    if not json_data:
        logger.error("Empty JSON data, skipping CSV conversion.")
        return
    
    try:
        df = pd.json_normalize(json_data)  # Flatten nested JSON
        df.columns = [clean_column_name(col) for col in df.columns]  # Rename columns
        df.to_csv(csv_output_path, index=False)
        print(f"CSV file saved at: {csv_output_path}")
    except Exception as e:
        logger.error(f"Error converting JSON to CSV: {e}")

def process_pdf_to_csv(pdf_path, csv_output_path):
    """Processes a PDF to extract text, get JSON from OpenAI, and save as CSV."""
    extracted_text = extract_text_from_pdf(pdf_path)
    json_data = openai_chat_completion(SYSTEM_PROMPT, extracted_text)
    json_to_csv(json_data, csv_output_path)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python pdf_to_csv_processor.py <pdf_path> <csv_output_path>")
    else:
        process_pdf_to_csv(sys.argv[1], sys.argv[2])
