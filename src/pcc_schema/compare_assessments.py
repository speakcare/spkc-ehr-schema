"""
Comparison script for SpeakCare chart data vs PCC assessment data.

This script converts SpeakCare chart internal_json to PCC-DB format and compares
it field-by-field with the actual PCC assessment data, generating a CSV report
of differences.
"""

import json
import csv
import argparse
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from pcc_schema.pcc_assessment_schema import PCCAssessmentSchema

logger = logging.getLogger(__name__)


def normalize_response_value(value: Any) -> str:
    """
    Normalize response values to strings, treating empty values consistently.
    
    Args:
        value: Response value (can be dict, string, None, etc.)
        
    Returns:
        Normalized string value, or empty string for empty values
    """
    if value is None:
        return ""
    
    if isinstance(value, dict):
        if not value or value == {}:
            return ""
        # If dict has response_value, use that
        if "response_value" in value:
            return str(value["response_value"]) if value["response_value"] else ""
        # Otherwise, treat non-empty dict as non-empty (edge case)
        return str(value)
    
    if isinstance(value, (list, tuple)):
        if not value:
            return ""
        # Join list items
        return ",".join(str(item) for item in value if item)
    
    # Convert to string, strip whitespace
    str_value = str(value).strip()
    return str_value


def is_empty(value: Any) -> bool:
    """
    Check if a value is empty after normalization.
    
    Args:
        value: Value to check
        
    Returns:
        True if value is empty (normalized), False otherwise
    """
    normalized = normalize_response_value(value)
    return normalized == ""


def extract_data_from_json(file_path: str) -> Dict[str, Any]:
    """
    Extract speakcare_chart and pcc_assessment data from JSON file.
    
    Args:
        file_path: Path to JSON file
        
    Returns:
        Dictionary with:
        - internal_json: Model output from speakcare_chart
        - schema_id: Template ID from speakcare_chart
        - table_name: Table name from speakcare_chart
        - assessment_id: Assessment ID key from pcc_assessment
        - patient_id: EHR patient ID from pcc_assessment
        - pcc_assessment: The actual PCC assessment object
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Extract speakcare_chart data
    speakcare_chart = data.get("speakcare_chart", {})
    json_internal_filled = speakcare_chart.get("json_internal_filled", [])
    
    if not json_internal_filled:
        raise ValueError("No json_internal_filled found in speakcare_chart")
    
    internal_json = json_internal_filled[0].get("internal_json")
    if not internal_json:
        raise ValueError("No internal_json found in json_internal_filled")
    
    schema_id = speakcare_chart.get("schema_id")
    if schema_id:
        # Convert string to int if needed
        try:
            schema_id = int(schema_id)
        except (ValueError, TypeError):
            pass
    
    table_name = speakcare_chart.get("table_name", "")
    
    # Extract pcc_assessment data
    pcc_assessment = data.get("pcc_assessment", {})
    if not pcc_assessment:
        raise ValueError("No pcc_assessment found in JSON")
    
    assessments = pcc_assessment.get("assessments", {})
    items = assessments.get("items", {})
    
    if not items:
        raise ValueError("No assessment items found in pcc_assessment")
    
    # Get the first (and typically only) assessment_id
    assessment_id_str = list(items.keys())[0]
    try:
        assessment_id = int(assessment_id_str)
    except (ValueError, TypeError):
        assessment_id = assessment_id_str
    
    patient_id = pcc_assessment.get("ehr_patient_id")
    if patient_id:
        try:
            patient_id = int(patient_id)
        except (ValueError, TypeError):
            pass
    
    pcc_assessment_obj = items[assessment_id_str]
    
    return {
        "internal_json": internal_json,
        "schema_id": schema_id,
        "table_name": table_name,
        "assessment_id": assessment_id,
        "patient_id": patient_id,
        "pcc_assessment": pcc_assessment_obj
    }


def convert_table_name_to_template_name(table_name: str) -> str:
    """
    Convert table name to template name format.
    
    Example: "MHCS Nursing Daily Skilled Note" -> "MHCS_Nursing_Daily_Skilled_Note"
    
    Args:
        table_name: Table name string
        
    Returns:
        Template name with underscores
    """
    # Replace spaces with underscores
    template_name = table_name.replace(" ", "_")
    return template_name


def convert_speakcare_to_pcc_db(
    internal_json: Dict[str, Any],
    schema_id: int,
    assessment_id: int,
    patient_id: int,
    table_name: str
) -> Dict[str, Any]:
    """
    Convert SpeakCare internal_json to PCC-DB format.
    
    Args:
        internal_json: Model output format from speakcare_chart
        schema_id: Template ID
        assessment_id: Assessment ID
        patient_id: Patient ID
        table_name: Table name (for template_name derivation)
        
    Returns:
        PCC-DB formatted dictionary
    """
    pcc_schema = PCCAssessmentSchema()
    
    template_name = convert_table_name_to_template_name(table_name)
    
    result = pcc_schema.format_to_pcc_db(
        assessment_identifier=schema_id,
        model_response=internal_json,
        assessment_id=assessment_id,
        patient_id=patient_id,
        template_name=template_name
    )
    
    return result


def extract_all_fields(pcc_db_obj: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Flatten PCC-DB formatted object into field dictionary.
    
    Args:
        pcc_db_obj: PCC-DB formatted object (from assessments.items[assessment_id])
        
    Returns:
        Dictionary with keys like "Cust_F_1:Does the resident have a respiratory diagnosis or symptoms?"
        and values containing response_value and response_text
    """
    fields = {}
    
    sections = pcc_db_obj.get("sections", [])
    
    for section in sections:
        assessment_question_groups = section.get("assessment_question_groups", [])
        
        for group in assessment_question_groups:
            assessment_responses = group.get("assessment_responses", [])
            
            for response in assessment_responses:
                question_key = response.get("question_key", "")
                question_text = response.get("question_text", "")
                
                if not question_key:
                    continue
                
                # Create field key
                field_key = f"{question_key}:{question_text}"
                
                # Extract response data
                responses_array = response.get("responses", [])
                
                # Get the first response (typically only one)
                response_data = {}
                if responses_array:
                    first_response = responses_array[0]
                    response_value = first_response.get("response_value", "")
                    response_text = first_response.get("response_text", "")
                    
                    response_data = {
                        "response_value": response_value,
                        "response_text": response_text
                    }
                else:
                    # Empty response
                    response_data = {
                        "response_value": "",
                        "response_text": ""
                    }
                
                fields[field_key] = response_data
    
    return fields


def compare_fields(
    speakcare_fields: Dict[str, Dict[str, Any]],
    pcc_fields: Dict[str, Dict[str, Any]]
) -> Dict[str, str]:
    """
    Compare SpeakCare fields with PCC fields and return differences.
    
    Only shows differences when SpeakCare has a non-empty value that differs from PCC.
    If SpeakCare is empty, the field is not included in the output.
    
    Args:
        speakcare_fields: Fields from converted SpeakCare data
        pcc_fields: Fields from PCC assessment
        
    Returns:
        Dictionary mapping field_key to difference string (e.g., '"a" != "b"')
    """
    differences = {}
    
    # Iterate through all SpeakCare fields
    for field_key, speakcare_data in speakcare_fields.items():
        speakcare_value = speakcare_data.get("response_value", "")
        speakcare_text = speakcare_data.get("response_text", "")
        
        # Normalize SpeakCare value
        speakcare_normalized = normalize_response_value(speakcare_value)
        
        # Skip if SpeakCare is empty (don't show as difference)
        if is_empty(speakcare_normalized):
            continue
        
        # Get corresponding PCC field
        pcc_data = pcc_fields.get(field_key, {})
        pcc_value = pcc_data.get("response_value", "")
        pcc_text = pcc_data.get("response_text", "")
        
        # Normalize PCC value
        pcc_normalized = normalize_response_value(pcc_value)
        
        # Compare values
        if speakcare_normalized != pcc_normalized:
            # Values differ - format difference
            diff_str = f'"{pcc_normalized}" != "{speakcare_normalized}"'
            differences[field_key] = diff_str
        elif speakcare_text and pcc_text and speakcare_text != pcc_text:
            # Values are same but response_text differs
            diff_str = f'"{pcc_normalized}" (text: "{pcc_text}") != "{speakcare_normalized}" (text: "{speakcare_text}")'
            differences[field_key] = diff_str
    
    return differences


def process_single_file(file_path: str) -> Tuple[Dict[str, str], Dict[str, Any]]:
    """
    Process a single JSON file and return comparison results.
    
    Args:
        file_path: Path to JSON file
        
    Returns:
        Tuple of (differences_dict, metadata_dict)
        differences_dict: {field_key: difference_string, ...}
        metadata_dict: {assessment_id, patient_id, assessment_key}
    """
    # Extract data
    extracted = extract_data_from_json(file_path)
    
    # Convert SpeakCare to PCC-DB format
    speakcare_pcc_db = convert_speakcare_to_pcc_db(
        internal_json=extracted["internal_json"],
        schema_id=extracted["schema_id"],
        assessment_id=extracted["assessment_id"],
        patient_id=extracted["patient_id"],
        table_name=extracted["table_name"]
    )
    
    # Get the assessment object from the converted result
    assessment_id_str = str(extracted["assessment_id"])
    speakcare_assessment = speakcare_pcc_db["assessments"]["items"][assessment_id_str]
    
    # Extract fields from both
    speakcare_fields = extract_all_fields(speakcare_assessment)
    pcc_fields = extract_all_fields(extracted["pcc_assessment"])
    
    # Compare
    differences = compare_fields(speakcare_fields, pcc_fields)
    
    # Create metadata
    metadata = {
        "assessment_id": extracted["assessment_id"],
        "patient_id": extracted["patient_id"],
        "assessment_key": f"{extracted['patient_id']}:{extracted['assessment_id']}"
    }
    
    return differences, metadata


def generate_comparison_csv_single(
    differences: Dict[str, str],
    output_path: str,
    assessment_key: str
):
    """
    Generate CSV for single file comparison.
    
    Args:
        differences: Dictionary of field_key -> difference_string
        output_path: Path to output CSV file
        assessment_key: Assessment key in format "patient_id:assessment_id"
    """
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        
        # Header
        writer.writerow(["fields", assessment_key])
        
        # Sort fields for consistent output
        sorted_fields = sorted(differences.keys())
        
        # Data rows
        for field_key in sorted_fields:
            diff_str = differences[field_key]
            writer.writerow([field_key, diff_str])


def process_directory(directory_path: str, output_csv: str):
    """
    Process all JSON files in a directory and generate aggregated CSV.
    
    Args:
        directory_path: Path to directory containing JSON files
        output_csv: Path to output CSV file
    """
    directory = Path(directory_path)
    json_files = list(directory.glob("*.json"))
    
    if not json_files:
        logger.warning(f"No JSON files found in {directory_path}")
        return
    
    # Process all files and collect differences
    all_differences = {}  # {assessment_key: {field_key: diff_str, ...}}
    all_fields = set()  # All unique field keys across all files
    
    for json_file in json_files:
        try:
            differences, metadata = process_single_file(str(json_file))
            assessment_key = metadata["assessment_key"]
            
            # Store differences for this assessment
            all_differences[assessment_key] = differences
            
            # Collect all field keys
            all_fields.update(differences.keys())
            
            logger.info(f"Processed {json_file.name}: {len(differences)} differences")
        except Exception as e:
            logger.error(f"Error processing {json_file.name}: {e}")
            continue
    
    # Generate CSV with all assessments
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        
        # Header: fields, then one column per assessment_key
        header = ["fields"] + list(sorted(all_differences.keys()))
        writer.writerow(header)
        
        # Sort fields for consistent output
        sorted_fields = sorted(all_fields)
        
        # Data rows
        for field_key in sorted_fields:
            row = [field_key]
            
            # Add difference for each assessment (empty if no difference for this field)
            for assessment_key in sorted(all_differences.keys()):
                diff_str = all_differences[assessment_key].get(field_key, "")
                row.append(diff_str)
            
            writer.writerow(row)
    
    logger.info(f"Generated comparison CSV: {output_csv}")


def main():
    """Main entry point for command-line interface."""
    parser = argparse.ArgumentParser(
        description="Compare SpeakCare chart data with PCC assessment data"
    )
    
    parser.add_argument(
        "--file",
        type=str,
        help="Path to single JSON file to process"
    )
    
    parser.add_argument(
        "--directory",
        type=str,
        help="Path to directory containing JSON files to process"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Path to output CSV file"
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if args.file:
        # Single file mode
        differences, metadata = process_single_file(args.file)
        generate_comparison_csv_single(
            differences,
            args.output,
            metadata["assessment_key"]
        )
        logger.info(f"Generated comparison CSV: {args.output}")
        logger.info(f"Found {len(differences)} differences")
        
    elif args.directory:
        # Directory mode
        process_directory(args.directory, args.output)
        
    else:
        parser.error("Either --file or --directory must be specified")


if __name__ == "__main__":
    main()
