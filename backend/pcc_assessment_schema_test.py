"""
Tests for PointClickCare Assessment Schema wrapper.
"""

import json
import unittest
import logging
from typing import Dict, Any

from pcc_assessment_schema import PCCAssessmentSchema, PCC_META_SCHEMA, extract_response_options


class TestPCCAssessmentSchema(unittest.TestCase):
    """Test cases for PCC Assessment Schema wrapper."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.pcc_schema = PCCAssessmentSchema()
        
        # MDS 2.0 Full Assessment test data (simplified version)
        self.mds_assessment = {
            "assessmentDescription": "MDS 2.0 Full Assessment",
            "facId": 100,
            "templateId": 1,
            "templateVersion": "2.0",
            "sections": [
                {
                    "sectionCode": "AA",
                    "sectionDescription": "Identification Information",
                    "sectionSequence": 40,
                    "assessmentQuestionGroups": [
                        {
                            "groupNumber": "1",
                            "groupText": "",
                            "groupTitle": "RESIDENT NAME",
                            "questions": [
                                {
                                    "questionKey": "AA1a",
                                    "questionNumber": "a",
                                    "questionText": "First",
                                    "questionTitle": "First Name",
                                    "questionType": "txt",
                                    "required": False,
                                    "length": 12,
                                    "range": "Text,sp(12)"
                                },
                                {
                                    "questionKey": "AA1c",
                                    "questionNumber": "c",
                                    "questionText": "Last",
                                    "questionTitle": "Last Name",
                                    "questionType": "txt",
                                    "required": True,
                                    "length": 18,
                                    "range": "Text"
                                }
                            ]
                        },
                        {
                            "groupNumber": "2",
                            "groupText": "",
                            "groupTitle": "GENDER",
                            "questions": [
                                {
                                    "questionKey": "AA2",
                                    "questionNumber": "",
                                    "questionText": "GENDER",
                                    "questionTitle": "GENDER",
                                    "questionType": "radh",
                                    "required": True,
                                    "length": 1,
                                    "range": "1,2,-",
                                    "responseOptions": [
                                        {
                                            "responseText": "Male",
                                            "responseValue": "1"
                                        },
                                        {
                                            "responseText": "Female",
                                            "responseValue": "2"
                                        }
                                    ]
                                }
                            ]
                        },
                        {
                            "groupNumber": "3",
                            "groupText": "",
                            "groupTitle": "BIRTHDATE",
                            "questions": [
                                {
                                    "questionKey": "AA3",
                                    "questionNumber": "",
                                    "questionText": "BIRTHDATE",
                                    "questionTitle": "BIRTHDATE",
                                    "questionType": "dte",
                                    "required": True,
                                    "length": 8,
                                    "range": "Valid full or partial date, -(8)"
                                }
                            ]
                        }
                    ]
                },
                {
                    "sectionCode": "AB",
                    "sectionDescription": "Demographic Information",
                    "sectionSequence": 50,
                    "assessmentQuestionGroups": [
                        {
                            "groupNumber": "2",
                            "groupText": "",
                            "groupTitle": "ADMITTED FROM (AT ENTRY)",
                            "questions": [
                                {
                                    "questionKey": "AB2",
                                    "questionNumber": "",
                                    "questionText": "ADMITTED FROM (AT ENTRY)",
                                    "questionTitle": "ADMITTED FROM (AT ENTRY)",
                                    "questionType": "rad",
                                    "required": True,
                                    "length": 1,
                                    "range": "1 thru 8,-",
                                    "responseOptions": [
                                        {
                                            "responseText": "Private home/apt. with no home health services",
                                            "responseValue": "1"
                                        },
                                        {
                                            "responseText": "Private home/apt. with home health services",
                                            "responseValue": "2"
                                        },
                                        {
                                            "responseText": "Board and care/assisted living/group home",
                                            "responseValue": "3"
                                        },
                                        {
                                            "responseText": "Nursing home",
                                            "responseValue": "4"
                                        },
                                        {
                                            "responseText": "Acute care hospital",
                                            "responseValue": "5"
                                        },
                                        {
                                            "responseText": "Psychiatric hospital, MR/DD facility",
                                            "responseValue": "6"
                                        },
                                        {
                                            "responseText": "Rehabilitation hospital",
                                            "responseValue": "7"
                                        },
                                        {
                                            "responseText": "Other",
                                            "responseValue": "8"
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                },
                {
                    "sectionCode": "A",
                    "sectionDescription": "Identification and Background Information",
                    "sectionSequence": 80,
                    "assessmentQuestionGroups": []  # Empty container
                }
            ]
        }
    
    def test_basic_registration(self):
        """Test basic assessment registration."""
        # Register the assessment
        assessment_id, assessment_name = self.pcc_schema.register_assessment(None, self.mds_assessment)
        self.assertIsInstance(assessment_id, int)
        self.assertEqual(assessment_name, "MDS 2.0 Full Assessment")
        
        # Verify it's registered
        assessments = self.pcc_schema.list_assessments()
        self.assertIn(assessment_id, assessments)
        
        # Verify JSON schema is generated
        json_schema = self.pcc_schema.get_json_schema(assessment_id)
        self.assertIsInstance(json_schema, dict)
        self.assertIn("properties", json_schema)
    
    def test_json_schema_structure(self):
        """Test JSON schema structure and nesting."""
        assessment_id, assessment_name = self.pcc_schema.register_assessment(None, self.mds_assessment)
        json_schema = self.pcc_schema.get_json_schema(assessment_id)
        
        # Verify title
        self.assertEqual(json_schema["title"], "MDS 2.0 Full Assessment")
        
        # Verify table_name field
        self.assertIn("table_name", json_schema["properties"])
        table_name_field = json_schema["properties"]["table_name"]
        self.assertEqual(table_name_field["type"], "string")
        self.assertEqual(table_name_field["const"], "MDS 2.0 Full Assessment")
        
        # Verify sections structure
        self.assertIn("sections", json_schema["properties"])
        sections = json_schema["properties"]["sections"]
        self.assertEqual(sections["type"], "object")
        self.assertFalse(sections["additionalProperties"])
        
        # Verify section properties exist (AA.Identification Information)
        self.assertIn("AA.Identification Information", sections["properties"])
        aa_section = sections["properties"]["AA.Identification Information"]
        self.assertEqual(aa_section["type"], "object")
        self.assertFalse(aa_section["additionalProperties"])
        
        # Verify assessmentQuestionGroups structure
        self.assertIn("assessmentQuestionGroups", aa_section["properties"])
        groups = aa_section["properties"]["assessmentQuestionGroups"]
        self.assertEqual(groups["type"], "object")
        self.assertFalse(groups["additionalProperties"])
        
        # Verify group properties exist (1)
        self.assertIn("1", groups["properties"])
        group1 = groups["properties"]["1"]
        self.assertEqual(group1["type"], "object")
        self.assertFalse(group1["additionalProperties"])
        
        # Verify questions structure
        self.assertIn("questions", group1["properties"])
        questions = group1["properties"]["questions"]
        self.assertEqual(questions["type"], "object")
        self.assertFalse(questions["additionalProperties"])
    
    def test_field_types(self):
        """Test different field types are correctly mapped."""
        assessment_id, assessment_name = self.pcc_schema.register_assessment(None, self.mds_assessment)
        json_schema = self.pcc_schema.get_json_schema(assessment_id)
        
        # Navigate to questions
        questions = json_schema["properties"]["sections"]["properties"]["AA.Identification Information"]["properties"]["assessmentQuestionGroups"]["properties"]["1"]["properties"]["questions"]["properties"]
        
        # Test text field (First Name)
        self.assertIn("First", questions)
        first_name_field = questions["First"]
        self.assertEqual(first_name_field["type"], ["string", "null"])
        
        # Test text field (Last Name)
        self.assertIn("Last", questions)
        last_name_field = questions["Last"]
        self.assertEqual(last_name_field["type"], ["string", "null"])
        
        # Navigate to GENDER questions
        gender_questions = json_schema["properties"]["sections"]["properties"]["AA.Identification Information"]["properties"]["assessmentQuestionGroups"]["properties"]["2"]["properties"]["questions"]["properties"]
        
        # Test radio field (GENDER)
        self.assertIn("GENDER", gender_questions)
        gender_field = gender_questions["GENDER"]
        self.assertEqual(gender_field["type"], ["string", "null"])
        self.assertIn("enum", gender_field)
        
        # Navigate to BIRTHDATE questions
        birthdate_questions = json_schema["properties"]["sections"]["properties"]["AA.Identification Information"]["properties"]["assessmentQuestionGroups"]["properties"]["3"]["properties"]["questions"]["properties"]
        
        # Test date field (BIRTHDATE)
        self.assertIn("BIRTHDATE", birthdate_questions)
        birthdate_field = birthdate_questions["BIRTHDATE"]
        self.assertEqual(birthdate_field["type"], ["string", "null"])
        self.assertIn("format", birthdate_field)
        self.assertEqual(birthdate_field["format"], "date")
    
    def test_options_extraction(self):
        """Test options extraction from responseOptions."""
        # Test extract_response_options function directly
        options = [
            {"responseText": "Male", "responseValue": "1"},
            {"responseText": "Female", "responseValue": "2"}
        ]
        extracted = extract_response_options(options)
        self.assertEqual(extracted, ["Male", "Female"])
        
        # Test with empty options
        empty_extracted = extract_response_options([])
        self.assertEqual(empty_extracted, [])
        
        # Test with None
        none_extracted = extract_response_options(None)
        self.assertEqual(none_extracted, [])
        
        # Test enum values in JSON schema
        assessment_id, assessment_name = self.pcc_schema.register_assessment(None, self.mds_assessment)
        json_schema = self.pcc_schema.get_json_schema(assessment_id)
        
        # Check GENDER field enum
        gender_field = json_schema["properties"]["sections"]["properties"]["AA.Identification Information"]["properties"]["assessmentQuestionGroups"]["properties"]["2"]["properties"]["questions"]["properties"]["GENDER"]
        self.assertIn("enum", gender_field)
        self.assertIn("Male", gender_field["enum"])
        self.assertIn("Female", gender_field["enum"])
        self.assertIn(None, gender_field["enum"])  # null should be included
        
        # Check ADMITTED FROM field enum
        admitted_from_field = json_schema["properties"]["sections"]["properties"]["AB.Demographic Information"]["properties"]["assessmentQuestionGroups"]["properties"]["2"]["properties"]["questions"]["properties"]["ADMITTED FROM (AT ENTRY)"]
        self.assertIn("enum", admitted_from_field)
        self.assertIn("Private home/apt. with no home health services", admitted_from_field["enum"])
        self.assertIn("Other", admitted_from_field["enum"])
        self.assertIn(None, admitted_from_field["enum"])
    
    def test_empty_containers(self):
        """Test handling of empty containers."""
        assessment_id, assessment_name = self.pcc_schema.register_assessment(None, self.mds_assessment)
        json_schema = self.pcc_schema.get_json_schema(assessment_id)
        
        # Verify empty section is handled gracefully
        sections = json_schema["properties"]["sections"]["properties"]
        
        # Section A should exist but have no assessmentQuestionGroups
        self.assertIn("A.Identification and Background Information", sections)
        section_a = sections["A.Identification and Background Information"]
        
        # Should have assessmentQuestionGroups property but it should be empty
        self.assertIn("assessmentQuestionGroups", section_a["properties"])
        groups = section_a["properties"]["assessmentQuestionGroups"]
        self.assertEqual(groups["type"], "object")
        self.assertEqual(groups["properties"], {})  # Empty properties
        self.assertEqual(groups["required"], [])  # Empty required
    
    def test_validation_success(self):
        """Test successful validation with valid data."""
        assessment_id, assessment_name = self.pcc_schema.register_assessment(None, self.mds_assessment)
        
        # Valid data matching the schema structure
        valid_data = {
            "table_name": "MDS 2.0 Full Assessment",
            "sections": {
                "AA.Identification Information": {
                    "assessmentQuestionGroups": {
                        "1": {
                            "questions": {
                                "First": "John",
                                "Last": "Doe"
                            }
                        },
                        "2": {
                            "questions": {
                                "GENDER": "Male"
                            }
                        },
                        "3": {
                            "questions": {
                                "BIRTHDATE": "1950-01-15"
                            }
                        }
                    }
                },
                "AB.Demographic Information": {
                    "assessmentQuestionGroups": {
                        "2": {
                            "questions": {
                                "ADMITTED FROM (AT ENTRY)": "Private home/apt. with no home health services"
                            }
                        }
                    }
                },
                "A.Identification and Background Information": {
                    "assessmentQuestionGroups": {}
                }
            }
        }
        
        is_valid, errors = self.pcc_schema.validate(assessment_id, valid_data)
        self.assertTrue(is_valid, f"Expected validation to pass, but got errors: {errors}")
    
    def test_validation_failure(self):
        """Test validation failure with invalid data."""
        assessment_id, assessment_name = self.pcc_schema.register_assessment(None, self.mds_assessment)
        
        # Invalid enum value for GENDER
        invalid_data = {
            "table_name": "MDS 2.0 Full Assessment",
            "sections": {
                "AA.Identification Information": {
                    "assessmentQuestionGroups": {
                        "2": {
                            "questions": {
                                "GENDER": "Invalid Gender"  # Not in enum
                            }
                        }
                    }
                }
            }
        }
        
        is_valid, errors = self.pcc_schema.validate(assessment_id, invalid_data)
        self.assertFalse(is_valid, "Expected validation to fail with invalid enum value")
        self.assertTrue(any("not one of" in error.lower() for error in errors), f"Expected enum error, got: {errors}")
        
        # Invalid date format
        invalid_date_data = {
            "table_name": "MDS 2.0 Full Assessment",
            "sections": {
                "AA.Identification Information": {
                    "assessmentQuestionGroups": {
                        "3": {
                            "questions": {
                                "BIRTHDATE": "not-a-date"  # Invalid date format
                            }
                        }
                    }
                }
            }
        }
        
        is_valid, errors = self.pcc_schema.validate(assessment_id, invalid_date_data)
        self.assertFalse(is_valid, "Expected validation to fail with invalid date")
    
    def test_field_metadata(self):
        """Test field metadata collection."""
        assessment_id, assessment_name = self.pcc_schema.register_assessment(None, self.mds_assessment)
        
        field_metadata = self.pcc_schema.get_field_metadata(assessment_id)
        
        # Should have metadata for all fields
        self.assertGreater(len(field_metadata), 0)
        
        # Find specific field metadata
        first_name_meta = next((field for field in field_metadata if field["key"] == "AA1a"), None)
        self.assertIsNotNone(first_name_meta, "Should have metadata for AA1a field")
        self.assertEqual(first_name_meta["name"], "First")
        self.assertEqual(first_name_meta["target_type"], "string")
        # level_keys should be ["AA", "1", "questions"] based on the actual schema structure
        self.assertEqual(first_name_meta["level_keys"], ["AA", "1", "questions"])
        
        # Check gender field metadata
        gender_meta = next((field for field in field_metadata if field["key"] == "AA2"), None)
        self.assertIsNotNone(gender_meta, "Should have metadata for AA2 field")
        self.assertEqual(gender_meta["name"], "GENDER")
        self.assertEqual(gender_meta["target_type"], "single_select")
        
        # Check birthdate field metadata
        birthdate_meta = next((field for field in field_metadata if field["key"] == "AA3"), None)
        self.assertIsNotNone(birthdate_meta, "Should have metadata for AA3 field")
        self.assertEqual(birthdate_meta["name"], "BIRTHDATE")
        self.assertEqual(birthdate_meta["target_type"], "date")

    def test_instruction_fields(self):
        """Test that instruction fields are properly mapped with const values."""
        assessment_with_instructions = {
            "assessmentDescription": "Test Assessment with Instructions",
            "facId": 100,
            "templateId": 1,
            "templateVersion": "1.0",
            "sections": [
                {
                    "sectionCode": "A",
                    "sectionDescription": "Test Section",
                    "assessmentQuestionGroups": [
                        {
                            "groupNumber": "1",
                            "groupTitle": "Test Group",
                            "questions": [
                                {
                                    "questionKey": "INSTR1",
                                    "questionNumber": "1",
                                    "questionText": "Please answer the following questions based on observation",
                                    "questionTitle": "Instructions",
                                    "questionType": "inst"
                                },
                                {
                                    "questionKey": "Q1",
                                    "questionNumber": "2",
                                    "questionText": "Patient height",
                                    "questionTitle": "Height",
                                    "questionType": "txt"
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        assessment_id, assessment_name = self.pcc_schema.register_assessment(None, assessment_with_instructions)
        json_schema = self.pcc_schema.get_json_schema(assessment_id)
        
        # Navigate to the questions - groupText is empty, so the key is just "1"
        questions = json_schema["properties"]["sections"]["properties"]["A.Test Section"]["properties"]["assessmentQuestionGroups"]["properties"]["1"]["properties"]["questions"]
        
        # Verify instruction field - property key is "1.Instructions"
        instr_field = questions["properties"]["1.Instructions"]
        self.assertEqual(instr_field["type"], "string")
        self.assertEqual(instr_field["const"], "Instructions.Please answer the following questions based on observation")
        self.assertEqual(instr_field["description"], "These are instructions that should be used as context for other properties of the same schema object and adjacent schema objects.")
        
        # Verify it's in the required list
        self.assertIn("1.Instructions", questions["required"])


if __name__ == "__main__":
    # Set up logging to see info messages
    logging.basicConfig(level=logging.INFO)
    unittest.main()
