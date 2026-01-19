"""
Tests for enriching PCC Assessment Schemas using CSV model instructions.

This test demonstrates using csv_to_dict to load model instructions from CSV files
and enrich the PCC schema with that data.
"""

import json
import unittest
import sys
import os
from pathlib import Path

# Add src directory to Python path
#sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'src'))

try:
    from jsonschema import Draft202012Validator
except ImportError:
    from jsonschema import Draft7Validator as Draft202012Validator

from pcc_schema.pcc_assessment_schema import PCCAssessmentSchema
from schema_engine.csv_to_dict import read_key_value_csv_path


class TestPCCEnrichmentFromCSV(unittest.TestCase):
    """Test enriching PCC schemas with CSV model instructions."""

    def setUp(self):
        """Set up test fixtures."""
        self.pcc_schema = PCCAssessmentSchema()
        self.test_dir = Path(__file__).parent
        self.templates_dir = self.test_dir.parent.parent / "src" / "pcc_schema" / "assmnt_templates"
        self.instructions_dir = self.test_dir / "model_instructions"
        
        # Define assessments to test
        # All CSVs now use "Key" column for keys and "Guidelines" column for values
        self.assessments = [
            {
                "name": "MHCS Nursing Weekly Skin Check",  # Matches template assessmentDescription
                "template_file": "MHCS_Nursing_Weekly_Skin_Check.json",
                "csv_file": "Assessment Table - Skin Assessment.csv",
                "csv_key_col": "Key",
                "csv_value_col": "Where in Database",
                "template_id": 21244831,
            },
            {
                "name": "MHCS Nursing Daily Skilled Note",
                "template_file": "MHCS_Nursing_Daily_Skilled_Note.json",
                "csv_file": "Assessment Table - Daily Skilled Nursing Note.csv",
                "csv_key_col": "Key",
                "csv_value_col": "Assumption Prompts, if not explicit in Transcript or Database",
                "template_id": 21242741,
            },
            {
                "name": "MHCS IDT 5 Day Section GG",
                "template_file": "MHCS_IDT_5_Day_Section_GG.json",
                "csv_file": "Assessment Table - ADL GG Comprehensive.csv",
                "csv_key_col": "Key",
                "csv_value_col": "Guidelines",
                "template_id": 21242733,
            },
            {
                "name": "MHCS Nursing Section GG",
                "template_file": "MHCS_Nursing_Section_GG.json",
                "csv_file": "Assessment Table - Nursing Section GG.csv",
                "csv_key_col": "Key",
                "csv_value_col": "Guidelines",
                "template_id": 21242851,
            },
            {
                "name": "MHCS Nursing Admission Assessment - V 5",
                "template_file": "MHCS_Nursing_Admission_Assessment_-_V_5.json",
                "csv_file": "Assessment Table - Admission Note.csv",
                "csv_key_col": "Key",
                "csv_value_col": "Guidelines",
                "template_id": 21244981,
            },
            {
                "name": "MHCS Nursing Monthly Summary",
                "template_file": "MHCS_Nursing_Monthly_Summary.json",
                "csv_file": "Assessment Table - Monthly Summary.csv",
                "csv_key_col": "Key",
                "csv_value_col": "Guidelines",
                "template_id": 21244911,
            },
        ]
    
    def _generate_dummy_csv_for_assessment(
        self,
        assessment_id: int,
        assessment_name: str,
        csv_filename: str,
        key_col: str = "Key",
        value_col: str = "Guidelines"
    ) -> Path:
        """
        Generate a realistic dummy CSV file for an assessment enrichment test.
        
        Args:
            assessment_id: The assessment template ID
            assessment_name: The assessment name
            csv_filename: The CSV filename to generate
            key_col: Column name for keys (default: "Key")
            value_col: Column name for values (default: "Guidelines")
            
        Returns:
            Path to the generated CSV file
        """
        import csv
        
        # Get field metadata
        field_metadata = self.pcc_schema.get_field_metadata(assessment_id)
        
        # Extract unique field keys
        field_keys = set()
        field_types = {}
        for field in field_metadata:
            field_key = field.get("key")
            if field_key:
                field_keys.add(field_key)
                # Store field type for generating appropriate enrichment text
                original_type = field.get("original_schema_type", "")
                target_type = field.get("target_type", "")
                field_types[field_key] = (original_type, target_type)
        
        # Generate enrichment text based on field type
        def get_enrichment_text(field_key: str) -> str:
            original_type, target_type = field_types.get(field_key, ("", ""))
            
            # Check original schema type first
            if original_type == "txt":
                return "Extract from transcript. Document any relevant observations or details mentioned."
            elif original_type == "dte":
                return "Extract date from transcript. Verify against database records if available."
            elif original_type in ("rad", "radh", "cmb"):
                return "Select appropriate option from transcript. Check database if not explicit in transcript."
            elif original_type in ("mcs", "mcsh"):
                return "Select all applicable options from transcript and database. Include all relevant selections."
            elif original_type == "chk":
                return "Check transcript for explicit mention. Default based on context if unclear."
            elif original_type in ("num", "numde"):
                return "Extract numeric value from transcript. Verify against database if available."
            elif original_type == "gbdy":
                return "Extract table entries from transcript. Document descriptions for each entry mentioned."
            # Fallback to target type
            elif target_type == "date":
                return "Extract date from transcript. Verify against database records if available."
            elif target_type == "single_select":
                return "Select appropriate option from transcript. Check database if not explicit in transcript."
            elif target_type == "multiple_select":
                return "Select all applicable options from transcript and database. Include all relevant selections."
            elif target_type == "checkbox":
                return "Check transcript for explicit mention. Default based on context if unclear."
            elif target_type in ("integer", "number", "positive_integer", "positive_number"):
                return "Extract numeric value from transcript. Verify against database if available."
            else:
                # Generic fallback
                return "Extract from transcript. Document any relevant observations or details mentioned."
        
        # Create CSV content
        csv_path = self.instructions_dir / csv_filename
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            # Write header
            writer.writerow([key_col, value_col])
            # Write rows for each field key
            for field_key in sorted(field_keys):
                enrichment_text = get_enrichment_text(field_key)
                writer.writerow([field_key, enrichment_text])
        
        return csv_path
    
    def test_register_and_enrich_all_assessments(self):
        """Test registering and enriching all PCC assessments with CSV data."""
        
        for assessment in self.assessments:
            with self.subTest(assessment=assessment["name"]):
                # Load assessment template
                template_path = self.templates_dir / assessment["template_file"]
                with open(template_path, "r", encoding="utf-8") as f:
                    template_data = json.load(f)
                
                # Register the assessment
                table_id, table_name = self.pcc_schema.register_assessment(
                    assessment["template_id"],
                    template_data
                )
                
                self.assertEqual(table_id, assessment["template_id"])
                self.assertEqual(table_name, assessment["name"])
                
                # Validate the schema BEFORE enrichment
                json_schema_before = self.pcc_schema.get_json_schema(table_id)
                try:
                    Draft202012Validator.check_schema(json_schema_before)
                except Exception as schema_error:
                    error_msg = str(schema_error)
                    if "non-unique elements" in error_msg:
                        self.fail(
                            f"JSON schema for {assessment['name']} is invalid BEFORE enrichment: "
                            f"duplicate property keys/names detected. Error: {schema_error}"
                        )
                    else:
                        self.fail(
                            f"JSON schema for {assessment['name']} is not valid BEFORE enrichment: {schema_error}"
                        )
                print(f"  ✓ {assessment['name']}: Schema is valid before enrichment")
                
                # Load CSV model instructions using csv_to_dict
                csv_file_path = self.instructions_dir / assessment["csv_file"]
                # Generate dummy CSV for Monthly Summary or Section GG if missing
                if not csv_file_path.exists() and assessment["template_id"] in (21244911, 21242851):
                    csv_file_path = self._generate_dummy_csv_for_assessment(
                        assessment["template_id"],
                        assessment["name"],
                        assessment["csv_file"],
                        key_col=assessment["csv_key_col"],
                        value_col=assessment["csv_value_col"]
                    )
                
                csv_path = str(csv_file_path)
                # Use wrapper to enrich directly from CSV
                unmatched_keys = self.pcc_schema.enrich_assessment_from_csv(
                    table_name,
                    csv_path=csv_path,
                    key_col=assessment["csv_key_col"],
                    value_col=assessment["csv_value_col"],
                    key_prefix="Cust",
                    sanitize_values=True,
                    skip_blank_keys=True,
                    strip_whitespace=True,
                    case_insensitive=False,
                    on_duplicate="concat",
                )
                
                # Verify we got enrichment data
                local_dict = read_key_value_csv_path(
                    csv_path,
                    key_col=assessment["csv_key_col"],
                    value_col=assessment["csv_value_col"],
                    key_prefix="Cust",
                    sanitize_values=True,
                    skip_blank_keys=True,
                    strip_whitespace=True,
                )
                self.assertGreater(len(local_dict), 0, 
                                   f"No enrichment data loaded from {assessment['csv_file']}")
                
                # Verify return type (positive/negative cases)
                self.assertIsInstance(unmatched_keys, list)
                
                # Log if there are unmatched keys (which might indicate CSV issues)
                if len(unmatched_keys) > 0:
                    print(f"  ⚠ {assessment['name']}: {len(unmatched_keys)} unmatched keys: {unmatched_keys}")
                else:
                    print(f"  ✓ {assessment['name']}: All keys matched")
                
                # Verify enrichment was applied
                json_schema_after = self.pcc_schema.get_json_schema(table_id)
                
                # Validate that the enriched JSON schema is still valid after enrichment
                try:
                    Draft202012Validator.check_schema(json_schema_after)
                except Exception as schema_error:
                    error_msg = str(schema_error)
                    if "non-unique elements" in error_msg:
                        self.fail(
                            f"JSON schema for {assessment['name']} became invalid AFTER enrichment: "
                            f"duplicate property keys/names detected. Error: {schema_error}"
                        )
                    else:
                        self.fail(
                            f"JSON schema for {assessment['name']} became invalid AFTER enrichment: {schema_error}"
                        )
                print(f"  ✓ {assessment['name']}: Schema is valid after enrichment")
                
                field_index = self.pcc_schema.get_field_metadata(table_id)
                
                # Count how many fields were enriched
                enriched_count = 0
                for field_meta in field_index:
                    field_key = field_meta.get("key")
                    # Retrieve description text by recomputing dictionary to check
                    # Note: For performance in real code, caller can reuse their dict
                    local_dict = read_key_value_csv_path(
                        csv_path,
                        key_col=assessment["csv_key_col"],
                        value_col=assessment["csv_value_col"],
                        key_prefix="Cust",
                        sanitize_values=True,
                        skip_blank_keys=True,
                        strip_whitespace=True,
                    )
                    if field_key in local_dict:
                        # Check if the field description was updated
                        level_keys = field_meta.get("level_keys", [])
                        property_key = field_meta.get("property_key")
                        
                        # Navigate to the property in json_schema_after
                        current = json_schema_after
                        for key in level_keys:
                            current = current.get("properties", {}).get(key, {})
                        
                        if property_key and "properties" in current:
                            prop_schema = current["properties"].get(property_key, {})
                            description = prop_schema.get("description", "")
                            if local_dict[field_key] in description:
                                enriched_count += 1
                
                # Verify that at least some fields were enriched
                self.assertGreater(enriched_count, 0,
                                   f"No fields were enriched for {assessment['name']}")
                
                print(f"✓ {assessment['name']}: {enriched_count} fields enriched from CSV")

    def test_enrich_skin_check_specific_fields(self):
        """Test enrichment of specific fields in the Skin Check assessment."""
        # Load and register Skin Check assessment
        template_path = self.templates_dir / "MHCS_Nursing_Weekly_Skin_Check.json"
        with open(template_path, "r", encoding="utf-8") as f:
            template_data = json.load(f)
        
        table_id, table_name = self.pcc_schema.register_assessment(21244831, template_data)
        
        # Load CSV enrichment data
        csv_path = str(self.instructions_dir / "MHCS_Nursing_Weekly_Skin_Check.csv")
        enrichment_dict = read_key_value_csv_path(
            csv_path,
            key_col="Key",
            value_col="Guidelines",
            key_prefix="Cust",
            sanitize_values=True,
        )
        
        # Verify specific keys are in enrichment dict
        self.assertIn("Cust_1_A", enrichment_dict)
        self.assertIn("Cust_1_B", enrichment_dict)
        
        # Verify the enrichment text was sanitized (no HTML/special chars)
        for key, value in enrichment_dict.items():
            self.assertNotIn("<", value, f"HTML tags not sanitized in {key}")
            self.assertNotIn(">", value, f"HTML tags not sanitized in {key}")
            self.assertNotIn('"', value, f"Quotes not sanitized in {key}")
        
        # Enrich the schema using the wrapper
        unmatched_keys = self.pcc_schema.enrich_assessment_from_csv(
            table_name,
            csv_path=csv_path,
            key_col="Key",
            value_col="Guidelines",
            key_prefix="Cust",
            sanitize_values=True,
            skip_blank_keys=True,
            strip_whitespace=True,
            on_duplicate="concat",
        )
        
        # Verify no unmatched keys
        self.assertEqual(len(unmatched_keys), 0)
        
        # Get the JSON schema and verify specific field was enriched
        json_schema = self.pcc_schema.get_json_schema(table_id)
        
        # Validate that the enriched JSON schema is a valid JSON Schema
        try:
            Draft202012Validator.check_schema(json_schema)
        except Exception as schema_error:
            self.fail(f"JSON schema for Skin Check is not valid: {schema_error}")
        
        field_index = self.pcc_schema.get_field_metadata(table_id)
        
        # Find field 1_A
        field_1a = next((f for f in field_index if f.get("key") == "Cust_1_A"), None)
        self.assertIsNotNone(field_1a, "Field Cust_1_A not found")
        
        # Navigate to the property
        level_keys = field_1a.get("level_keys", [])
        property_key = field_1a.get("property_key")
        
        current = json_schema
        for key in level_keys:
            current = current.get("properties", {}).get(key, {})
        
        prop_schema = current["properties"].get(property_key, {})
        description = prop_schema.get("description", "")
        
        # Verify enrichment text is in description
        self.assertIn(enrichment_dict["Cust_1_A"], description)
        print(f"✓ Field 'Cust_1_A' enriched with: {enrichment_dict['Cust_1_A'][:50]}...")

    def test_enrich_daily_skilled_note(self):
        """Test enriching Daily Skilled Note assessment with Guidelines column."""
        # Load and register Daily Skilled Note assessment
        template_path = self.templates_dir / "MHCS_Nursing_Daily_Skilled_Note.json"
        with open(template_path, "r", encoding="utf-8") as f:
            template_data = json.load(f)
        
        table_id, table_name = self.pcc_schema.register_assessment(21242741, template_data)
        
        # Load CSV data - we'll use Guidelines column for enrichment
        csv_path = str(self.instructions_dir / "MHCS_Nursing_Daily_Skilled_Note.csv")
        
        # Enrich the schema using the wrapper
        unmatched_keys = self.pcc_schema.enrich_assessment_from_csv(
            table_name,
            csv_path=csv_path,
            key_col="Key",
            value_col="Guidelines",
            key_prefix="Cust",
            sanitize_values=True,
            skip_blank_keys=True,
            strip_whitespace=True,
            on_duplicate="concat",
        )
        
        # Verify return type and that we got a list (may have unmatched keys if CSV has extra entries)
        self.assertIsInstance(unmatched_keys, list)
        
        # Verify enrichment
        json_schema = self.pcc_schema.get_json_schema(table_id)
        field_index = self.pcc_schema.get_field_metadata(table_id)
        
        # Build local dict for verification
        enrichment_dict = read_key_value_csv_path(
            csv_path,
            key_col="Key",
            value_col="Guidelines",
            key_prefix="Cust",
            sanitize_values=True,
        )

        # Check a specific field
        if "Cust_A_1" in enrichment_dict:
            field_a1 = next((f for f in field_index if f.get("key") == "Cust_A_1"), None)
            if field_a1:
                level_keys = field_a1.get("level_keys", [])
                property_key = field_a1.get("property_key")
                
                current = json_schema
                for key in level_keys:
                    current = current.get("properties", {}).get(key, {})
                
                prop_schema = current["properties"].get(property_key, {})
                description = prop_schema.get("description", "")
                
                # Verify enrichment text is in description
                self.assertIn(enrichment_dict["Cust_A_1"], description)
                print(f"✓ Field 'Cust_A_1' enriched with Guidelines column")

    def test_csv_key_prefix_functionality(self):
        """Test that key_prefix correctly prepends 'Cust_' to CSV keys."""
        csv_path = str(self.instructions_dir / "MHCS_Nursing_Weekly_Skin_Check.csv")
        
        # Read without prefix
        without_prefix = read_key_value_csv_path(
            csv_path,
            key_col="Key",
            value_col="Guidelines",
            key_prefix=None,
            sanitize_values=False,
        )
        
        # Read with prefix
        with_prefix = read_key_value_csv_path(
            csv_path,
            key_col="Key",
            value_col="Guidelines",
            key_prefix="Cust",
            sanitize_values=False,
        )
        
        # Verify the prefix was added
        for key in without_prefix:
            prefixed_key = f"Cust_{key}"
            self.assertIn(prefixed_key, with_prefix, 
                          f"Expected {prefixed_key} to be in prefixed dict")
            self.assertEqual(without_prefix[key], with_prefix[prefixed_key],
                            f"Values should match for {key}")
        
        print(f"✓ Key prefix functionality verified: {len(without_prefix)} keys prefixed")

    def test_enrichment_with_invalid_keys(self):
        """Test enrichment with invalid keys to verify unmatched_keys detection (negative case)."""
        # Load and register Skin Check assessment
        template_path = self.templates_dir / "MHCS_Nursing_Weekly_Skin_Check.json"
        with open(template_path, "r", encoding="utf-8") as f:
            template_data = json.load(f)
        
        table_id, table_name = self.pcc_schema.register_assessment(21244831, template_data)
        
        # Create enrichment dict with some valid and some invalid keys
        enrichment_dict = {
            "Cust_1_A": "Valid enrichment text",
            "Cust_1_B": "Another valid enrichment",
            "Cust_invalid_key_1": "This key does not exist",
            "Cust_invalid_key_2": "This key also does not exist",
        }
        
        # Enrich the schema
        unmatched_keys = self.pcc_schema.engine.enrich_schema(table_name, enrichment_dict)
        
        # Verify that invalid keys were detected (negative case)
        self.assertIsInstance(unmatched_keys, list)
        self.assertEqual(len(unmatched_keys), 2)
        self.assertIn("Cust_invalid_key_1", unmatched_keys)
        self.assertIn("Cust_invalid_key_2", unmatched_keys)
        self.assertNotIn("Cust_1_A", unmatched_keys)
        self.assertNotIn("Cust_1_B", unmatched_keys)
        
        # Verify that valid fields were still enriched
        json_schema = self.pcc_schema.get_json_schema(table_id)
        field_index = self.pcc_schema.get_field_metadata(table_id)
        
        # Check that Cust_1_A was enriched
        field_1a = next((f for f in field_index if f.get("key") == "Cust_1_A"), None)
        self.assertIsNotNone(field_1a)
        
        level_keys = field_1a.get("level_keys", [])
        property_key = field_1a.get("property_key")
        
        current = json_schema
        for key in level_keys:
            current = current.get("properties", {}).get(key, {})
        
        prop_schema = current["properties"].get(property_key, {})
        description = prop_schema.get("description", "")
        
        # Verify the valid enrichment was applied
        self.assertIn(enrichment_dict["Cust_1_A"], description)
        
        print(f"✓ Negative case verified: {len(unmatched_keys)} unmatched keys detected")


if __name__ == "__main__":
    unittest.main()

