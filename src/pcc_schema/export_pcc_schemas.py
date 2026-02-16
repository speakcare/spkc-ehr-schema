#!/usr/bin/env python3
"""
Export JSON schemas for all PCC assessment templates.

This script initializes PCCAssessmentSchema, retrieves the JSON schema
for each registered assessment template using get_json_schema(), and
saves them to JSON files in the test_outputs/ directory.
"""

import json
import os
import re
import sys
from pathlib import Path

# Add src directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from pcc_schema.pcc_assessment_schema import PCCAssessmentSchema


def sanitize_filename(name: str) -> str:
    """
    Sanitize a name for use in a filename.
    
    Args:
        name: The name to sanitize
        
    Returns:
        Sanitized name safe for use in filenames
    """
    # Replace spaces and special characters with underscores
    sanitized = re.sub(r'[^\w\s-]', '', name)
    sanitized = re.sub(r'[-\s]+', '_', sanitized)
    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')
    return sanitized


def export_pcc_schemas(output_dir: str = "test_outputs") -> None:
    """
    Export JSON schemas for all PCC assessment templates.
    
    Args:
        output_dir: Directory to save the JSON schema files (default: "test_outputs")
    """
    # Ensure output directory exists
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Initialize PCC Assessment Schema (automatically loads all templates)
    print("Initializing PCC Assessment Schema...")
    pcc_schema = PCCAssessmentSchema()
    
    # Get list of all registered assessments
    assessments = pcc_schema.list_assessments_info()
    print(f"Found {len(assessments)} registered assessments\n")
    
    # Export each assessment's JSON schema
    for assessment in assessments:
        assessment_id = assessment["id"]
        assessment_name = assessment["name"]
        
        print(f"Exporting schema for assessment {assessment_id}: {assessment_name}")
        
        try:
            # Get JSON schema using get_json_schema
            json_schema = pcc_schema.get_json_schema(assessment_id)
            
            # Create filename: {template_id}_{sanitized_name}_schema.json
            sanitized_name = sanitize_filename(assessment_name)
            filename = f"{assessment_id}_{sanitized_name}_schema.json"
            filepath = output_path / filename
            
            # Write JSON schema to file with proper indentation
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(json_schema, f, indent=2, ensure_ascii=False)
            
            print(f"  ✓ Saved to: {filepath}")
            
        except KeyError as e:
            print(f"  ✗ Error: Assessment {assessment_id} not found: {e}")
        except Exception as e:
            print(f"  ✗ Error exporting {assessment_id}: {e}")
    
    print(f"\nExport complete! Schemas saved to {output_path.absolute()}")


if __name__ == "__main__":
    export_pcc_schemas()
